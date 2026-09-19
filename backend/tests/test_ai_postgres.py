"""Opt-in PostgreSQL proof, isolated in a temporary schema, never public tables.

Run AI_TEST_POSTGRES=1 uv run pytest tests/test_ai_postgres.py -q. Uses the backend
DATABASE_URL; the role needs CREATE SCHEMA. No credentials are printed.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.core.database import Base
from app.core.migrations import upgrade_ai_schema
from app.models.user import User
from app.models.school import School
from app.models.ai_account import AIUsage, CreditTransaction
from app.services.ai.credits import CreditService
from app.services.ai.errors import AIError
from tests.test_ai_credits import record_call

@pytest.mark.skipif(os.environ.get('AI_TEST_POSTGRES') != '1', reason='opt-in isolated PostgreSQL schema')
def test_postgres_migration_concurrency_and_settlement():
    assert settings.DATABASE_URL.startswith('postgresql')
    schema = 'ai_test_' + uuid4().hex
    url = make_url(settings.DATABASE_URL)
    if os.environ.get('AI_TEST_POSTGRES_HOST'):
        url = url.set(host=os.environ['AI_TEST_POSTGRES_HOST'])
    admin = create_engine(url)
    engine = None
    created = False
    try:
        with admin.begin() as db:
            db.exec_driver_sql(f'CREATE SCHEMA {schema}')
        created = True
        engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
        tables = [table for table in Base.metadata.sorted_tables if table.name not in {'ai_usage', 'credit_transactions', 'user_subscriptions'}]
        Base.metadata.create_all(engine, tables=tables)
        with engine.begin() as db:
            db.execute(User.__table__.insert().values(id=1, email='pg@example.test', name='PG', role='teacher'))
        upgrade_ai_schema(engine)
        upgrade_ai_schema(engine)
        accounts = CreditService(sessionmaker(engine, expire_on_commit=False))
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: accounts.account(1), range(2)))
        assert accounts.account(1)['credit_balance'] == 50
        accounts.adjust(1, reset_to=10)
        def reserve(_):
            try:
                return accounts.reserve(1, 'exam_generation')
            except AIError as error:
                assert error.code == 'INSUFFICIENT_CREDITS'
        with ThreadPoolExecutor(max_workers=2) as pool:
            requests = list(pool.map(reserve, range(2)))
        assert len([item for item in requests if item]) == 1
        request = next(item for item in requests if item)
        record_call(accounts, request)
        with ThreadPoolExecutor(max_workers=2) as pool:
            finished = list(pool.map(lambda _: accounts.finish(request, success=False), range(2)))
        assert sorted(finished) == [False, True]
        assert accounts.account(1)['credit_balance'] == 10
        request = accounts.reserve(1, 'exam_generation')
        record_call(accounts, request)
        accounts.finish(request, success=True)
        assert accounts.account(1)['credit_balance'] == 0
        with accounts.sessions() as db:
            assert db.scalar(select(func.sum(CreditTransaction.amount))) == 0
            assert db.get(AIUsage, request).credits_charged == 10
        # Reporting aggregates and audited account edits use the same SQL on PG.
        from app.services.ai.reporting import report
        from app.api.routes.usage_reports import SubscriptionUpdate, update_subscription
        from app.models.audit_log import AuditLog
        from fastapi import HTTPException
        with accounts.sessions.begin() as db:
            db.add(User(id=2, email='admin-pg@example.test', name='Admin PG', role='super_admin'))
        with accounts.sessions() as db:
            actor = db.get(User, 2)
            snapshot = report(db, actor)
            assert snapshot['summary']['requests'] == 2
            assert snapshot['summary']['provider_calls'] == 2
            assert snapshot['summary']['credits_charged'] == 10
            change = SubscriptionUpdate(plan='PRO', status='active', credit_allowance=200,
                                        credit_adjustment=5, settings_version=1, reason='Isolated PG proof')
            result = update_subscription(1, change, actor, db)
            assert result['credit_balance'] == 5 and result['credit_allowance'] == 200
            with pytest.raises(HTTPException) as conflict:
                update_subscription(1, change, actor, db)
            assert conflict.value.status_code == 409
            assert db.scalar(select(func.count()).select_from(AuditLog)) == 1
        # Same idempotency key under concurrent transactions reserves once.
        from app.services.ai.credits import RequestReplay, utcnow
        from app.services.ai.operator import recover
        from datetime import timedelta
        accounts.adjust(1, amount=20)
        def deduplicated(_):
            try:
                return accounts.reserve(1, 'exam_generation', lease_owner='worker',
                                        idempotency_key='pg-same-key', fingerprint='same')
            except RequestReplay as replay:
                return replay.request_id
        with ThreadPoolExecutor(max_workers=2) as pool:
            identical = list(pool.map(deduplicated, range(2)))
        assert identical[0] == identical[1]
        with accounts.sessions.begin() as db:
            row = db.get(AIUsage, identical[0])
            row.lease_expires_at = utcnow() - timedelta(seconds=1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            recovered = list(pool.map(lambda _: recover(accounts, actor_id=2, apply=True), range(2)))
        assert sum(len(result['request_ids']) for result in recovered) == 1
        assert accounts.read_account(1)['credit_balance'] == 25
        assert not accounts.heartbeat(identical[0], 'worker')
        assert not accounts.finish(identical[0], success=True, lease_owner='worker')
    finally:
        if engine:
            engine.dispose()
        if created:
            with admin.begin() as db:
                db.exec_driver_sql(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
        admin.dispose()
