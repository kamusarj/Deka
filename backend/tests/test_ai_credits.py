from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select, update
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.config import settings
from app.models.user import User
from app.models.school import School  # register legacy FK
from app.models.ai_account import AIUsage, CreditTransaction, UserSubscription
from app.services.ai.credits import CreditService, utcnow
from app.services.ai.errors import AIError
from app.services.ai.gateway import AIResponse, TokenUsage
from app.services.ai.usage import UsageRecorder

@pytest.fixture
def accounts(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path}/accounts.db', connect_args={'check_same_thread': False, 'timeout': 15})
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add(User(id=1, email='teacher@example.test', name='Teacher', role='teacher'))
        db.add(User(id=2, email='other@example.test', name='Other', role='teacher'))
    monkeypatch.setattr(settings, 'ENABLE_CREDIT_SYSTEM', True)
    yield CreditService(factory)
    engine.dispose()


def record_call(accounts, request_id, error=None):
    UsageRecorder(accounts.sessions, 1, request_id, 'exam_generation')(
        AIResponse('private', 'openai', 'test', TokenUsage(100, 20, 0), 5, 'upstream'), error)


def assert_balance(accounts, expected):
    assert accounts.account(1)['credit_balance'] == expected
    with accounts.sessions() as db:
        assert db.scalar(select(func.sum(CreditTransaction.amount)).where(CreditTransaction.user_id == 1)) == expected


def test_success_settles_once_and_tracks_usage(accounts):
    request_id = accounts.reserve(1, 'exam_generation')
    assert_balance(accounts, 40)
    record_call(accounts, request_id)
    assert accounts.finish(request_id, success=True)
    assert not accounts.finish(request_id, success=False)
    assert_balance(accounts, 40)
    with accounts.sessions() as db:
        summary = db.get(AIUsage, request_id)
        assert summary.status == 'success'
        assert summary.credits_charged == 10
        assert summary.input_tokens == 100
        assert summary.provider == 'openai'
        assert len(db.scalars(select(AIUsage)).all()) == 2


def test_failure_refunds_and_records_failed_attempt(accounts):
    request_id = accounts.reserve(1, 'exam_generation')
    record_call(accounts, request_id, AIError('AI_TIMEOUT'))
    assert accounts.finish(request_id, success=False, error_code='AI_TIMEOUT')
    assert not accounts.finish(request_id, success=False)
    assert_balance(accounts, 50)
    with accounts.sessions() as db:
        rows = db.scalars(select(AIUsage)).all()
        assert all(row.status == 'failed' and row.credits_charged == 0 for row in rows)


def test_insufficient_does_not_create_reservation(accounts):
    accounts.adjust(1, reset_to=9)
    with pytest.raises(AIError, match='INSUFFICIENT_CREDITS'):
        accounts.reserve(1, 'exam_generation')
    assert_balance(accounts, 9)
    with accounts.sessions() as db:
        assert db.scalar(select(func.count()).select_from(AIUsage)) == 0


def test_concurrent_first_enrollment_and_reservations(accounts):
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: accounts.account(1), range(2)))
    assert_balance(accounts, 50)
    accounts.adjust(1, reset_to=10)
    def reserve(_):
        try:
            return accounts.reserve(1, 'exam_generation')
        except AIError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, range(2)))
    assert len([item for item in results if item]) == 1
    assert_balance(accounts, 0)
    request_id = next(item for item in results if item)
    with ThreadPoolExecutor(max_workers=2) as pool:
        finishes = list(pool.map(lambda _: accounts.finish(request_id, success=False), range(2)))
    assert sorted(finishes) == [False, True]
    assert_balance(accounts, 10)


def test_renewal_is_once_and_plan_changes_do_not_mint_credits(accounts):
    accounts.change_plan(1, 'BASIC')
    accounts.change_plan(1, 'PRO')
    assert_balance(accounts, 50)
    with accounts.sessions.begin() as db:
        db.execute(update(UserSubscription).values(current_period_end=utcnow() - timedelta(days=1)))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: accounts.account(1), range(2)))
    assert_balance(accounts, 1550)


def test_disabled_credits_still_records_usage(accounts, monkeypatch):
    monkeypatch.setattr(settings, 'ENABLE_CREDIT_SYSTEM', False)
    request_id = accounts.reserve(1, 'exam_generation')
    record_call(accounts, request_id)
    accounts.finish(request_id, success=True)
    assert_balance(accounts, 50)


def test_reset_refuses_pending_and_preserves_ledger(accounts):
    request_id = accounts.reserve(1, 'exam_generation')
    with pytest.raises(ValueError, match='pending'):
        accounts.adjust(1, reset_to=100)
    accounts.finish(request_id, success=False)
    accounts.adjust(1, amount=-5)
    assert_balance(accounts, 45)
    accounts.adjust(1, reset_to=100)
    assert_balance(accounts, 100)
