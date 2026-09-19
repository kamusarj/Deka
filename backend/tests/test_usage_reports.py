from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import get_db
from app.main import app
from app.models.ai_account import AIUsage, CreditTransaction, UserSubscription
from app.models.audit_log import AuditLog
from app.models.school import School
from app.models.user import User
from app.services.ai.credits import utcnow
from app.services.auth_service import create_access_token
from tests.test_ai_credits import accounts


@pytest.fixture
def client(accounts):
    with accounts.sessions.begin() as db:
        db.add(School(id=1, name='School One'))
        db.add(School(id=2, name='School Two'))
        db.flush()
        db.get(User, 1).school_id = 1
        db.get(User, 2).school_id = 2
        db.add_all([User(id=3, email='root@test.local', name='Root', role='super_admin'),
                    User(id=4, email='school@test.local', name='School', role='school_admin', school_id=1),
                    User(id=5, email='view@test.local', name='Viewer', role='viewer', school_id=1),
                    User(id=6, email='unknown@test.local', name='Unknown', role='unknown')])
    def database():
        with accounts.sessions() as db:
            yield db
    app.dependency_overrides[get_db] = database
    with TestClient(app) as result:
        yield result
    app.dependency_overrides.pop(get_db, None)


def auth(user_id):
    # Deliberately incorrect JWT role: current database role must win.
    return {'Authorization': 'Bearer ' + create_access_token(user_id, 'super_admin')}


def payload(**changes):
    return dict(plan='BASIC', status='active', credit_allowance=750, credit_adjustment=20,
                settings_version=0, reason='Custom teacher allowance', **changes) if not changes else {**payload(), **changes}


def seed_usage(accounts):
    accounts.account(1)
    with accounts.sessions.begin() as db:
        for owner in [1, 2, 3, 4, 5]:
            db.add(AIUsage(id=f'req-{owner}', request_id=f'req-{owner}', user_id=owner, record_kind='request',
                           operation='exam_generation', status='success', credits_charged=10, input_tokens=100,
                           output_tokens=20, estimated_cost_usd=Decimal('0.1')))
            db.add(AIUsage(id=f'call-{owner}', request_id=f'req-{owner}', user_id=owner, record_kind='provider',
                           operation='exam_generation', status='success', provider='openai', model='test',
                           input_tokens=100, output_tokens=20, estimated_cost_usd=Decimal('0.1')))
        db.add(AIUsage(id='failed', request_id='failed', user_id=1, record_kind='request', operation='exam_generation', status='failed'))
        db.add(AIUsage(id='unknown', request_id='failed', user_id=1, record_kind='provider', operation='exam_generation', status='failed'))


def test_catalog_public_and_shared(client):
    from app.services.ai.pricing import PLAN_ALLOWANCES
    result = client.get('/api/subscription-plans')
    assert result.status_code == 200
    assert {p['id']: p['monthly_credits'] for p in result.json()['plans']} == PLAN_ALLOWANCES
    assert 'provider' not in result.text and 'key' not in result.text
    assert client.get('/api/usage/report').status_code == 401
    assert client.get('/api/usage/report', headers=auth(6)).status_code == 403


@pytest.mark.parametrize('user_id,expected', [(1, {1}), (2, {2}), (3, {1,2,3,4,5,6}), (4, {1,4}), (5, {5})])
def test_scope_and_target_bypass(client, accounts, user_id, expected):
    seed_usage(accounts)
    result = client.get('/api/usage/report', headers=auth(user_id))
    assert result.status_code == 200, result.text
    assert {row['id'] for row in result.json()['users']} == expected
    for target in range(1, 7):
        status = 200 if target in expected else 404
        assert client.get(f'/api/usage/users/{target}', headers=auth(user_id)).status_code == status
        assert client.get('/api/usage/report', params={'user_id': target}, headers=auth(user_id)).status_code == status


def test_correct_aggregation_pagination_filters_and_unknown_cost(client, accounts):
    seed_usage(accounts)
    result = client.get('/api/usage/report', headers=auth(3), params={'limit': 2}).json()
    summary = result['summary']
    assert summary['requests'] == 6 and summary['success'] == 5 and summary['failed'] == 1
    assert summary['credits_charged'] == 50 and summary['provider_calls'] == 6
    assert summary['input_tokens'] == 500 and summary['output_tokens'] == 100
    assert Decimal(summary['known_cost_usd']) == Decimal('0.5')
    assert summary['estimated_cost_usd'] is None and summary['unpriced_calls'] == 1
    assert summary['unknown_token_calls'] == 1 and summary['active_users'] == 5
    assert len(result['users']) == 2 and result['total_users'] == 6
    assert sum(row['requests'] for row in result['roles']) == 6
    assert sum(row['requests'] for row in result['daily']) == 6
    next_page = client.get('/api/usage/report', headers=auth(3), params={'limit': 2, 'offset': 2}).json()
    assert not {u['id'] for u in result['users']} & {u['id'] for u in next_page['users']}
    filtered = client.get('/api/usage/report', headers=auth(3), params={'role': 'teacher', 'search': 'other@'}).json()
    assert filtered['total_users'] == 1 and filtered['summary']['requests'] == 1
    assert Decimal(filtered['summary']['estimated_cost_usd']) == Decimal('0.1')
    assert client.get('/api/usage/report', headers=auth(3), params={'search': '%'}).json()['total_users'] == 0
    yesterday = (utcnow() - timedelta(days=1)).date().isoformat()
    assert client.get('/api/usage/report', headers=auth(3), params={'date_to': yesterday}).json()['summary']['requests'] == 0
    assert client.get('/api/usage/report', headers=auth(3), params={'date_from': '2026-10-01', 'date_to': '2026-09-01'}).status_code == 422
    # Reports never silently create subscriptions for the listed accounts.
    with accounts.sessions() as db:
        assert db.scalar(select(func.count()).select_from(UserSubscription)) == 1


@pytest.mark.parametrize('actor', [1,2,4,5,6])
def test_only_super_admin_can_mutate(client, actor):
    assert client.patch('/api/admin/users/1/subscription', json=payload(), headers=auth(actor)).status_code == 403


def test_atomic_override_audit_ledger_and_stale_retry(client, accounts):
    response = client.patch('/api/admin/users/1/subscription', json=payload(), headers=auth(3))
    assert response.status_code == 200, response.text
    account = response.json()
    assert (account['plan'], account['credit_allowance'], account['credit_balance'], account['settings_version']) == ('BASIC',750,70,2)
    assert client.patch('/api/admin/users/1/subscription', json=payload(), headers=auth(3)).status_code == 409
    # Plan change alone does not reset balance or issue more credits.
    response = client.patch('/api/admin/users/1/subscription', json=payload(settings_version=2, plan='PRO', credit_adjustment=0, status='paused'), headers=auth(3))
    assert response.status_code == 200 and response.json()['credit_balance'] == 70
    from app.services.ai.errors import AIError
    with pytest.raises(AIError, match='SUBSCRIPTION_INACTIVE'):
        accounts.reserve(1, 'exam_generation')
    with accounts.sessions() as db:
        assert db.scalar(select(func.sum(CreditTransaction.amount)).where(CreditTransaction.user_id == 1)) == 70
        events = db.scalars(select(AuditLog).where(AuditLog.action == 'subscription.updated')).all()
        assert len(events) == 2 and events[0].actor_user_id == 3
        assert events[0].details['before']['credit_balance'] == 50
        assert events[0].details['after']['credit_allowance'] == 750


def test_invalid_balance_rollback_and_concurrent_save(client, accounts):
    accounts.account(1)
    bad = client.patch('/api/admin/users/1/subscription', json=payload(settings_version=1, credit_adjustment=-100), headers=auth(3))
    assert bad.status_code == 409
    assert accounts.account(1)['settings_version'] == 1
    def save(_):
        return client.patch('/api/admin/users/1/subscription', json=payload(settings_version=1), headers=auth(3)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, range(2))) == [200,409]
    assert accounts.account(1)['credit_balance'] == 70
    for changes in [{'credit_adjustment': 1.5}, {'credit_allowance': -1}, {'plan':'MADEUP'}, {'reason':'  '}, {'role':'super_admin'}]:
        assert client.patch('/api/admin/users/1/subscription', json=payload(**changes), headers=auth(3)).status_code == 422


def test_audit_failure_rolls_back_settings_and_balance(client, accounts, monkeypatch):
    from app.api.routes import usage_reports
    accounts.account(1)
    def fail_audit(*args, **kwargs):
        raise RuntimeError('audit storage unavailable')
    monkeypatch.setattr(usage_reports, 'record_audit', fail_audit)
    with pytest.raises(RuntimeError, match='audit storage unavailable'):
        client.patch('/api/admin/users/1/subscription', json=payload(settings_version=1), headers=auth(3))
    account = accounts.account(1)
    assert account['settings_version'] == 1 and account['credit_balance'] == 50 and account['plan'] == 'FREE'
    with accounts.sessions() as db:
        assert db.scalar(select(func.count()).select_from(CreditTransaction).where(CreditTransaction.type == 'adjustment')) == 0
