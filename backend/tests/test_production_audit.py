"""Production audit regressions with synthetic accounts, no paid provider access."""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace as NS
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, update
from app.core.config import settings
from app.models.ai_account import AIUsage, UserSubscription, CreditTransaction
from app.models.user import User
from app.models.exam import Exam
from app.models.document_cleanup import DocumentCleanup
from app.services.ai.credits import utcnow, next_month, RequestReplay, MAX_CREDIT_BALANCE
from app.services.ai.errors import AIError
from app.services.ai.operations import BillableOperation, replay_result
from app.services.ai.operator import recover
from app.services.ai.gateway import AIGateway
from app.services.ai.reporting import report
from app.services.exam_service import ExamService
from tests.test_ai_credits import accounts, record_call, assert_balance
from tests.test_ai_gateway import Transport
from tests.test_usage_reports import client, auth, seed_usage


@pytest.mark.parametrize('disabled', [False, True])
def test_unknown_operation_never_enrolls_or_reserves(accounts, monkeypatch, disabled):
    monkeypatch.setattr(settings, 'ENABLE_CREDIT_SYSTEM', not disabled)
    with pytest.raises(AIError, match='AI_OPERATION_NOT_CONFIGURED'):
        accounts.reserve(1, 'exam_generatoin')
    with accounts.sessions() as db:
        assert db.scalar(select(func.count()).select_from(UserSubscription)) == 0
        assert db.scalar(select(func.count()).select_from(CreditTransaction)) == 0


def test_free_policy_still_records_calls_and_pause_is_enforced(accounts):
    request = accounts.reserve(1, 'rag_query')
    record_call(accounts, request)
    accounts.finish(request, success=True)
    assert_balance(accounts, 50)
    with accounts.sessions.begin() as db:
        db.get(UserSubscription, 1).status = 'paused'
    with pytest.raises(AIError, match='SUBSCRIPTION_INACTIVE'):
        accounts.reserve(1, 'rag_query')


def test_read_account_does_not_enroll_or_renew(accounts):
    assert accounts.read_account(1) is None
    accounts.account(1)
    with accounts.sessions.begin() as db:
        account = db.scalar(select(UserSubscription).where(UserSubscription.user_id == 1))
        account.current_period_end = utcnow() - timedelta(days=400)
    assert accounts.read_account(1)['renewal_due']
    assert accounts.read_account(1)['credit_balance'] == 50
    request = accounts.reserve(1, 'rag_query')
    accounts.finish(request, success=True)
    assert accounts.read_account(1)['credit_balance'] == 100
    assert not accounts.read_account(1)['renewal_due']
    assert next_month(datetime(2028, 1, 31, tzinfo=timezone.utc)).day == 29
    assert next_month(datetime(2027, 1, 31, tzinfo=timezone.utc)).day == 28
    assert next_month(datetime(2027, 12, 31, tzinfo=timezone.utc)).year == 2028


def forbidden_fields(value):
    forbidden = {'provider', 'model', 'provider_request_id', 'input_tokens', 'output_tokens',
                 'cached_tokens', 'estimated_cost_usd', 'known_cost_usd', 'unpriced_calls', 'unknown_token_calls'}
    if isinstance(value, dict):
        assert not forbidden.intersection(value)
        for child in value.values():
            forbidden_fields(child)
    elif isinstance(value, list):
        for child in value:
            forbidden_fields(child)


@pytest.mark.parametrize('user_id', [1, 4, 5])
def test_nested_response_fields_never_depend_on_ui(client, accounts, monkeypatch, user_id):
    from app.api.routes import ai_account
    monkeypatch.setattr(ai_account, 'CreditService', lambda: accounts)
    seed_usage(accounts)
    for path in ['/api/usage/report', f'/api/usage/users/{user_id}', '/api/me/usage']:
        response = client.get(path, headers=auth(user_id))
        assert response.status_code == 200, response.text
        forbidden_fields(response.json())
    assert client.get('/api/me/usage?kind=provider', headers=auth(user_id)).status_code == 403
    response = client.get('/api/usage/users/1', headers=auth(3)).json()
    assert 'input_tokens' in response['summary'] and 'provider' in response['items'][0]


def test_deleted_user_history_and_attempt_day_are_preserved(client, accounts):
    seed_usage(accounts)
    with accounts.sessions.begin() as db:
        db.get(User, 2).deleted_at = utcnow()
        db.get(AIUsage, 'call-2').created_at = utcnow() + timedelta(days=1)
    with accounts.sessions() as db:
        root, school = db.get(User, 3), db.get(User, 4)
        today = report(db, root)
        assert today['summary']['requests'] == 6  # deleted user's request remains
        assert today['summary']['provider_calls'] == 5  # late attempt is tomorrow
        assert 2 not in {user['id'] for user in today['users']}
        tomorrow = (utcnow() + timedelta(days=1)).date()
        later = report(db, root, tomorrow, tomorrow)
        assert later['summary']['requests'] == 0 and later['summary']['provider_calls'] == 1
        assert Decimal(later['summary']['estimated_cost_usd']) == Decimal('0.1')
        assert report(db, school)['summary']['requests'] == 3
        assert today['role_semantics'] == 'current' and today['includes_deleted_history']


def test_reserved_credit_headroom_cannot_be_spent_by_admin_grant(accounts):
    accounts.adjust(1, reset_to=MAX_CREDIT_BALANCE)
    request = accounts.reserve(1, 'exam_generation')
    with pytest.raises(ValueError, match='limit'):
        accounts.adjust(1, amount=1)
    accounts.finish(request, success=False)
    assert_balance(accounts, MAX_CREDIT_BALANCE)


def add_root(accounts):
    with accounts.sessions.begin() as db:
        db.add(User(id=3, email='operator@example.test', name='Operator', role='super_admin'))


def expire(accounts, request_id):
    with accounts.sessions.begin() as db:
        db.get(AIUsage, request_id).lease_expires_at = utcnow() - timedelta(seconds=1)


def exam_row():
    return Exam(owner_user_id=1, school='Synthetic', grade=8, subject='KHTN', exam_type='test',
                duration_minutes=45, school_year='2026', total_score=10,
                matrix=[], summary={}, specification=[], questions=[], answer_key=[], rubric=[], validation={})


@pytest.mark.asyncio
async def test_result_commit_and_credit_settle_are_one_transaction(accounts):
    add_root(accounts)
    billing = BillableOperation(1, credits=accounts, idempotency_key='same-key', payload={'topic': 'test'})
    async def invoke():
        AIGateway().generate(prompt='fixture', provider='openai', service=Transport())
        with accounts.sessions() as db:
            exam = exam_row()
            db.add(exam)
            ExamService._commit_exam(db)
            db.refresh(exam)
            return exam
    result = await billing.run(invoke)
    assert_balance(accounts, 40)
    with accounts.sessions() as db:
        request = db.get(AIUsage, billing.request_id)
        assert request.status == 'success' and request.result_exam_id == result.id
        assert request.result_version == result.version_id
        actor = db.get(User, 1)
    with pytest.raises(RequestReplay):
        BillableOperation(1, credits=accounts, idempotency_key='same-key', payload={'topic': 'test'})
    with pytest.raises(AIError, match='AI_IDEMPOTENCY_CONFLICT'):
        BillableOperation(1, credits=accounts, idempotency_key='same-key', payload={'topic': 'other'})
    assert replay_result(actor, billing.request_id, accounts).id == result.id
    assert recover(accounts, actor_id=3, apply=True)['request_ids'] == []


@pytest.mark.asyncio
async def test_crash_before_commit_rolls_back_exam_and_recovery_fences_worker(accounts):
    add_root(accounts)
    billing = BillableOperation(1, credits=accounts)
    record_call(accounts, billing.request_id)
    with accounts.sessions() as db:
        exam = exam_row()
        db.add(exam)
        billing.persist(db, exam)
        db.rollback()  # process dies before the transaction commits
    with accounts.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Exam)) == 0
        assert db.get(AIUsage, billing.request_id).status == 'reserved'
    assert recover(accounts, actor_id=3, apply=True)['request_ids'] == []
    expire(accounts, billing.request_id)
    assert recover(accounts, actor_id=3)['request_ids'] == [billing.request_id]
    assert accounts.read_account(1)['credit_balance'] == 40
    assert recover(accounts, actor_id=3, apply=True)['request_ids'] == [billing.request_id]
    assert recover(accounts, actor_id=3, apply=True)['request_ids'] == []
    with pytest.raises(AIError, match='AI_REQUEST_FENCED'):
        billing.checkpoint()
    with accounts.sessions() as db:
        db.add(exam_row())
        with pytest.raises(AIError, match='AI_REQUEST_FENCED'):
            billing.persist(db, exam_row())
    record_call(accounts, billing.request_id)  # late upstream cost remains visible
    assert_balance(accounts, 50)
    billing.release()


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['locked', 'role', 'token', 'paused'])
async def test_authority_change_during_provider_does_not_publish(accounts, change):
    billing = BillableOperation(1, credits=accounts)
    async def invoke():
        AIGateway().generate(prompt='fixture', provider='openai', service=Transport())
        with accounts.sessions.begin() as db:
            actor = db.get(User, 1)
            if change == 'locked': actor.is_active = False
            if change == 'role': actor.role = 'viewer'
            if change == 'token': actor.token_version += 1
            if change == 'paused': db.get(UserSubscription, 1).status = 'paused'
        with accounts.sessions() as db:
            db.add(exam_row())
            ExamService._commit_exam(db)
    with pytest.raises(AIError):
        await billing.run(invoke)
    assert accounts.read_account(1)['credit_balance'] == 50
    with accounts.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Exam)) == 0


def test_kill_switch_and_concurrency_reject_before_reserve(accounts, monkeypatch):
    monkeypatch.setattr(settings, 'AI_ACCEPT_NEW_REQUESTS', False)
    with pytest.raises(AIError, match='AI_ADMISSION_CLOSED'):
        BillableOperation(1, credits=accounts)
    assert accounts.read_account(1) is None
    monkeypatch.setattr(settings, 'AI_ACCEPT_NEW_REQUESTS', True)
    first = BillableOperation(1, credits=accounts)
    try:
        with pytest.raises(AIError, match='AI_CAPACITY_EXCEEDED'):
            BillableOperation(1, credits=accounts)
    finally:
        first.finish(False); first.release()


def test_archive_path_and_decompression_limits():
    from app.extractors.document_extractors import validate_container, InvalidDocumentError
    for filename, content in [('../escape.xml', b'harmless'), ('word/document.xml', b'a' * 500000)]:
        data = BytesIO()
        with ZipFile(data, 'w', ZIP_DEFLATED) as archive:
            archive.writestr(filename, content)
        with pytest.raises(InvalidDocumentError):
            validate_container('docx', data.getvalue())
    with pytest.raises(InvalidDocumentError):
        validate_container('pdf', b'not a PDF')


def test_cleanup_retry_only_deletes_target(accounts, tmp_path, monkeypatch):
    from app.services import document_cleanup
    first, other = tmp_path/'deleted.pdf', tmp_path/'keep.pdf'
    first.write_bytes(b'synthetic'); other.write_bytes(b'keep')
    with accounts.sessions.begin() as db:
        job = DocumentCleanup(document_id=15, owner_user_id=1, stored_filename=first.name)
        db.add(job); db.flush(); job_id = job.id
    def offline(*args): raise ConnectionError('fixture')
    monkeypatch.setattr(document_cleanup, 'delete_document_vectors', offline)
    assert not document_cleanup.cleanup_one(accounts.sessions, job_id, upload_dir=tmp_path)
    assert not first.exists() and other.exists()
    called = []
    monkeypatch.setattr(document_cleanup, 'delete_document_vectors', lambda *args: called.append(args))
    assert document_cleanup.cleanup_one(accounts.sessions, job_id, upload_dir=tmp_path)
    assert document_cleanup.cleanup_one(accounts.sessions, job_id, upload_dir=tmp_path)
    assert called == [(15, 1), (15, 1)] and other.exists()


def test_totp_standard_vector_replay_and_recovery(client, accounts, monkeypatch):
    import time
    from app.services import admin_mfa
    from app.services.auth_service import hash_password
    from app.models.admin_mfa import AdminMFA
    # RFC 6238 SHA1 vector at 59 seconds (6-digit truncation).
    assert admin_mfa.totp('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', 1) == '287082'
    with accounts.sessions.begin() as db:
        db.get(User, 3).password_hash = hash_password('synthetic-password')
    proof = {'password': 'synthetic-password'}
    setup = client.post('/api/auth/mfa/setup', headers=auth(3), json=proof)
    assert setup.status_code == 200, setup.text
    secret = setup.json()['secret']
    with accounts.sessions() as db:
        assert secret not in db.get(AdminMFA, 3).encrypted_secret
    code = admin_mfa.totp(secret, int(time.time()//30))
    result = client.post('/api/auth/mfa/verify', headers=auth(3), json={**proof, 'code': code})
    assert result.status_code == 200, result.text
    recovery = result.json()['recovery_codes']
    assert len(recovery) == 10
    assert client.post('/api/auth/mfa/verify', headers=auth(3), json={**proof, 'code': code}).status_code == 400
    assert client.post('/api/auth/mfa/verify', headers=auth(3), json={**proof, 'code': recovery[0]}).status_code == 200
    assert client.post('/api/auth/mfa/verify', headers=auth(3), json={**proof, 'code': recovery[0]}).status_code == 400
    monkeypatch.setattr(settings, 'ENV', 'production')
    assert client.get('/api/usage/report', headers=auth(3)).status_code == 403
    upgraded = {'Authorization': 'Bearer ' + result.json()['access_token']}
    assert client.get('/api/usage/report', headers=upgraded).status_code == 200
    assert client.get('/api/auth/me', headers=auth(3)).status_code == 200


def test_body_limit_and_readiness_never_call_provider(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.http_limits import BodyLimitMiddleware
    from app.main import app
    small = FastAPI()
    small.add_middleware(BodyLimitMiddleware, max_bytes=5)
    @small.post('/body')
    async def body(): pytest.fail('Oversized input must not reach the route')
    response = TestClient(small).post('/body', content=b'123456')
    assert response.status_code == 413
    from app.core import database
    monkeypatch.setattr(database, 'get_session_factory', lambda: (_ for _ in ()).throw(ConnectionError('fixture')))
    client = TestClient(app)
    assert client.get('/health').status_code == 200
    assert client.get('/ready').status_code == 503
    assert 'fixture' not in client.get('/ready').text


@pytest.mark.asyncio
async def test_stream_projection_hides_nested_diagnostics(accounts):
    import json
    from app.services.ai.operations import billable_stream
    async def source():
        yield 'data: ' + json.dumps({'stage': 'verify', 'status': 'completed', 'data': {
            'reviews': [{'provider': 'secret-provider', 'model': 'secret-model', 'label': 'secret-label', 'pass': True}]}}) + '\n\n'
        yield 'data: ' + json.dumps({'type': 'result', 'payload': {'publication_status': 'verified'}}) + '\n\n'
    events = [event async for event in billable_stream(NS(id=1, role='teacher', school_id=None, token_version=0), source, accounts)]
    assert 'secret-provider' not in ''.join(events) and 'secret-model' not in ''.join(events)
    assert '"pass": true' in events[0]


def test_explicit_provider_allowlist_blocks_before_transport(monkeypatch):
    from app.services.ai_runtime import track_call
    monkeypatch.setattr(settings, 'AI_ALLOWED_PROVIDERS', ['openai'])
    with pytest.raises(AIError, match='AI_PROVIDER_NOT_ALLOWED'):
        with track_call('gemini', 'fixture', 'review'):
            pytest.fail('Rejected provider must not run')


def test_legacy_schema_startup_cannot_silently_upgrade(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect
    from app.core.migrations import check_schema
    engine = create_engine(f'sqlite:///{tmp_path}/empty.db')
    with pytest.raises(RuntimeError, match='incompatible'):
        check_schema(engine)
    assert inspect(engine).get_table_names() == []
    engine.dispose()


def test_revision_marker_does_not_hide_missing_columns(tmp_path):
    from sqlalchemy import create_engine, text
    from app.core.migrations import upgrade_ai_schema, check_schema
    engine = create_engine(f'sqlite:///{tmp_path}/damaged.db')
    upgrade_ai_schema(engine)
    check_schema(engine)
    with engine.begin() as db:
        db.execute(text('ALTER TABLE users DROP COLUMN token_version'))
    with pytest.raises(RuntimeError, match='columns incompatible: users'):
        check_schema(engine)
    engine.dispose()


@pytest.mark.asyncio
async def test_cancelled_await_keeps_provider_slot_until_thread_exits(monkeypatch):
    from threading import BoundedSemaphore, Event
    from app.services import resource_capacity
    monkeypatch.setattr(resource_capacity, '_provider_slots', BoundedSemaphore(1))
    started, stop = Event(), Event()
    def sdk():
        with resource_capacity.provider_slot():
            started.set()
            assert stop.wait(5)
    task = asyncio.create_task(asyncio.to_thread(sdk))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(AIError, match='AI_CAPACITY_EXCEEDED'):
            with resource_capacity.provider_slot():
                pytest.fail('Cancelled SDK still occupies capacity')
    finally:
        stop.set()


def test_restore_reconciles_current_deletion_and_rejects_owner_conflict(accounts):
    from app.services.deletion_journal import reconcile
    from app.models.document import UploadedDocument
    with accounts.sessions.begin() as db:
        db.add(User(id=8, email='operator@example.test', name='Operator', role='super_admin'))
    entry = {'document_id': 999, 'owner_user_id': 1, 'stored_filename': 'synthetic.txt'}
    assert reconcile(accounts.sessions, [entry], actor_id=8)['dry_run']
    with accounts.sessions() as db:
        assert db.scalar(select(func.count()).select_from(DocumentCleanup)) == 0
    reconcile(accounts.sessions, [entry], actor_id=8, apply=True)
    reconcile(accounts.sessions, [entry], actor_id=8, apply=True)
    with accounts.sessions() as db:
        assert db.scalar(select(func.count()).select_from(DocumentCleanup)) == 1
    with pytest.raises(ValueError, match='Conflicting deletion evidence'):
        reconcile(accounts.sessions, [{**entry, 'owner_user_id': 2}], actor_id=8, apply=True)


def test_registration_email_failure_keeps_unverified_account(client, monkeypatch):
    from app.api.routes import auth as routes
    def unavailable(*args, **kwargs):
        raise HTTPException(503, 'SMTP fixture unavailable')
    # Patch the route's delivery boundary, not the account transaction.
    monkeypatch.setattr(routes, 'send_account_email', unavailable)
    response = client.post('/api/auth/register', json={
        'name': 'Synthetic registrant', 'email': 'smtp-failure@example.com',
        'password': 'Audit-password-184!'})
    assert response.status_code == 201, response.text
    assert response.json()['email_delivery_pending'] is True
    assert 'SMTP fixture' not in response.text


def test_source_sharing_revocation_fences_persistence(accounts):
    from app.models.school import School
    from app.models.document import UploadedDocument
    with accounts.sessions.begin() as db:
        db.add(School(id=7, name='Synthetic school'))
        db.flush()
        db.get(User, 1).school_id = 7
        db.get(User, 2).school_id = 7
        db.add(UploadedDocument(id=50, owner_user_id=2, school_id=7, filename='shared.txt',
            stored_filename='shared.txt', file_type='txt', sharing_scope='school'))
    operation = BillableOperation(1, credits=accounts, actor=NS(id=1, role='teacher', school_id=7, token_version=0),
                                  payload={'document_ids': [50]})
    try:
        operation.checkpoint()
        with accounts.sessions.begin() as db:
            db.get(UploadedDocument, 50).sharing_scope = 'private'
        with pytest.raises(AIError, match='AI_AUTHORIZATION_CHANGED'):
            with accounts.sessions.begin() as db:
                operation.persist(db, Exam())
        operation.finish(False, 'AI_AUTHORIZATION_CHANGED')
        assert_balance(accounts, 50)
    finally:
        operation.release()


def test_operation_releases_authentication_read_transaction(accounts):
    with accounts.sessions() as db:
        actor = db.get(User, 1)
        assert db.in_transaction()
        operation = BillableOperation(1, credits=accounts, actor=actor)
        try:
            assert not db.in_transaction()
            operation.checkpoint()
            operation.finish(False, 'AI_CANCELLED')
        finally:
            operation.release()
