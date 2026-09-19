"""Real PostgreSQL process-death and legacy migration checks in disposable schemas."""
import os
import signal
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.migrations import upgrade_ai_schema, check_schema
from app.models.user import User
from app.models.exam import Exam
from app.models.document import UploadedDocument
from app.models.ai_account import AIUsage, CreditTransaction
from app.services.ai.credits import CreditService, utcnow
from app.services.ai.operator import recover

@pytest.fixture
def database():
    if os.environ.get('AI_TEST_POSTGRES') != '1':
        pytest.skip('opt-in isolated PostgreSQL schema')
    url = make_url(settings.DATABASE_URL)
    assert url.drivername.startswith('postgresql')
    schema = 'ai_crash_' + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.exec_driver_sql(f'CREATE SCHEMA {schema}')
    scoped = url.update_query_dict({'options': f'-csearch_path={schema}'})
    engine = create_engine(scoped)
    try:
        yield engine, scoped
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.exec_driver_sql(f'DROP SCHEMA {schema} CASCADE')
        admin.dispose()

@pytest.mark.parametrize('commit_before_kill', [False, True])
def test_process_kill_atomic_result_and_recovery(database, commit_before_kill):
    engine, url = database
    upgrade_ai_schema(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    accounts = CreditService(sessions)
    with sessions.begin() as db:
        db.add_all([User(id=1,email='teacher@example.test',name='Teacher',role='teacher'),
                    User(id=3,email='admin@example.test',name='Admin',role='super_admin')])
    env = os.environ.copy()
    env.update(DATABASE_URL=url.render_as_string(hide_password=False), ENV='test', USE_POSTGRES='true',
               CRASH_COMMIT=str(int(commit_before_kill)))
    code = '''
import os, signal
from app.services.ai.credits import CreditService
from app.services.ai.operations import BillableOperation
from tests.test_ai_credits import record_call
from tests.test_production_audit import exam_row
accounts=CreditService()
billing=BillableOperation(1, credits=accounts, idempotency_key='killed-process', payload={})
record_call(accounts,billing.request_id)
with accounts.sessions() as db:
    exam=exam_row(); db.add(exam); billing.persist(db,exam)
    if os.environ['CRASH_COMMIT']=='1': db.commit()
    os.kill(os.getpid(),signal.SIGKILL)
'''
    result = subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,timeout=30)
    assert result.returncode == -signal.SIGKILL, 'Synthetic worker did not reach kill point'
    with sessions.begin() as db:
        row = db.scalar(select(AIUsage).where(AIUsage.idempotency_key == 'killed-process'))
        request_id = row.id
        assert row.status == ('success' if commit_before_kill else 'reserved')
        assert db.scalar(select(func.count()).select_from(Exam)) == int(commit_before_kill)
        if commit_before_kill:
            assert db.get(Exam,row.result_exam_id).version_id == row.result_version
        row.lease_expires_at = utcnow() - timedelta(seconds=1)
    assert recover(accounts,actor_id=3,apply=True)['request_ids'] == ([] if commit_before_kill else [request_id])
    assert accounts.read_account(1)['credit_balance'] == (40 if commit_before_kill else 50)
    assert recover(accounts,actor_id=3,apply=True)['request_ids'] == []


def test_versioned_legacy_upgrade_preserves_data(database):
    from alembic import command
    from alembic.config import Config
    engine, _ = database
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    with engine.begin() as db:
        config.attributes['connection'] = db
        command.upgrade(config, '0003_subscription_version')
        db.execute(User.__table__.insert().values(id=1,email='legacy@example.test',name='Legacy',role='teacher'))
        db.execute(UploadedDocument.__table__.insert().values(id=2,owner_user_id=1,filename='legacy.txt',
            stored_filename='legacy.txt',file_type='txt',size=9,extracted_text='synthetic',status='ready'))
    accounts = CreditService(sessionmaker(engine,expire_on_commit=False))
    accounts.account(1)
    accounts.adjust(1,amount=7)
    upgrade_ai_schema(engine)
    check_schema(engine)
    with accounts.sessions() as db:
        assert db.get(UploadedDocument,2).owner_user_id == 1
        assert db.get(User,1).email == 'legacy@example.test'
        assert db.scalar(select(func.sum(CreditTransaction.amount))) == 57
    assert accounts.read_account(1)['credit_balance'] == 57
