import json
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import get_db
from app.main import app
from app.models.user import User
from app.models.ai_account import AIUsage
from app.schemas.exam import FullExamResponse
from app.services.auth_service import hash_password, create_access_token
from app.services.ai.gateway import AIGateway
from app.services.ai.errors import AIError
from tests.test_ai_credits import accounts, assert_balance
from tests.test_ai_gateway import Transport
from tests.test_exam_draft_persistence import request_payload

@pytest.fixture
def client(accounts, monkeypatch):
    from app.services.ai import operations
    from app.api.routes import ai_account
    monkeypatch.setattr(operations, 'CreditService', lambda: accounts)
    monkeypatch.setattr(ai_account, 'CreditService', lambda: accounts)
    def database():
        with accounts.sessions() as db:
            yield db
    app.dependency_overrides[get_db] = database
    with accounts.sessions.begin() as db:
        db.get(User, 1).password_hash = hash_password('development-password')
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


def headers(user_id=1):
    return {'Authorization': 'Bearer ' + create_access_token(user_id, 'teacher')}


def test_login_subscription_and_credit_visibility(client):
    response = client.post('/api/auth/login', json={'email': 'teacher@example.test', 'password': 'development-password'})
    assert response.status_code == 200
    auth = {'Authorization': 'Bearer ' + response.json()['access_token']}
    assert client.get('/api/me/subscription', headers=auth).json() is None
    assert client.get('/api/me/credits', headers=auth).json()['balance'] == 0
    for path in ['subscription', 'credits', 'usage']:
        assert client.get('/api/me/' + path).status_code == 401


def test_real_http_boundary_records_usage_and_refunds_failure(client, accounts, monkeypatch):
    from app.api.routes import exams
    async def fail(*args, **kwargs):
        class Broken(Transport):
            def generate_text(self, prompt):
                raise TimeoutError('sensitive upstream error')
        AIGateway().generate(prompt='sensitive document', provider='deepseek', service=Broken())
    monkeypatch.setattr(exams.exam_service, 'generate_full_exam', fail)
    result = client.post('/api/exams/generate-full-exam', headers=headers(), json=request_payload(allow_provider_fallback=False).model_dump())
    assert result.status_code == 504
    assert result.json()['detail']['code'] == 'AI_TIMEOUT'
    assert 'sensitive' not in result.text
    assert_balance(accounts, 50)
    usage = client.get('/api/me/usage', headers=headers()).json()['items']
    assert len(usage) == 1 and usage[0]['status'] == 'failed'
    request_id = usage[0]['request_id']
    assert client.get('/api/me/usage', headers=headers(), params={'kind': 'provider', 'request_id': request_id}).status_code == 403
    assert client.get('/api/me/usage', headers=headers(2), params={'request_id': request_id}).json()['items'] == []
    with accounts.sessions() as db:
        calls = db.scalars(select(AIUsage).where(AIUsage.record_kind == 'provider')).all()
        assert len(calls) == 1 and calls[0].provider == 'deepseek'



def test_http_and_stream_success_charge_once_each(client, accounts, monkeypatch):
    from app.api.routes import exams
    result = FullExamResponse(id=1, publication_status='verified', exam_info={}, matrix=[], summary={},
                              specification=[], questions=[], answer_key=[], rubric=[], validation={})
    async def generate(*args, **kwargs):
        AIGateway().generate(prompt='private', provider='openai', service=Transport())
        return result
    async def stream(*args, **kwargs):
        await generate()
        yield 'data: ' + json.dumps({'type': 'result', 'payload': result.model_dump(mode='json')}) + '\n\n'
    monkeypatch.setattr(exams.exam_service, 'generate_full_exam', generate)
    monkeypatch.setattr(exams.exam_service, 'generate_full_exam_stream', stream)
    payload = request_payload(allow_provider_fallback=False).model_dump()
    for path in ['/api/exams/generate-full-exam', '/api/exams/generate-full-exam/stream']:
        response = client.post(path, headers=headers(), json=payload)
        assert response.status_code == 200
    assert_balance(accounts, 30)
    items = client.get('/api/me/usage', headers=headers()).json()['items']
    assert len(items) == 2
    assert all(row['credits_charged'] == 10 and 'input_tokens' not in row for row in items)
    assert client.get('/api/me/credits', headers=headers(2)).json()['balance'] == 0


def test_http_insufficient_never_calls_exam(client, accounts, monkeypatch):
    from app.api.routes import exams
    accounts.adjust(1, reset_to=1)
    async def unexpected(*args, **kwargs):
        pytest.fail('exam must not run')
    monkeypatch.setattr(exams.exam_service, 'generate_full_exam', unexpected)
    response = client.post('/api/exams/generate-full-exam', headers=headers(), json=request_payload(allow_provider_fallback=False).model_dump())
    assert response.status_code == 402
    assert response.json()['detail']['code'] == 'INSUFFICIENT_CREDITS'
