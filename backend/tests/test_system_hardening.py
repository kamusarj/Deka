"""Security, concurrency, and fail-closed regression proof for US-117."""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import IntegrityError

from app.api.routes import documents as document_routes
from app.core import database
from app.core.config import INSECURE_DEFAULT_SECRET_KEY, Settings, settings
from app.main import app
from app.models.exam import Exam
from app.models.user import User
from app.services import auth_service
from app.services import exam_service as exam_service_module
from app.services.exam_service import ExamService
from app.services import rate_limit as rate_limit_module
from app.services.oauth_service import find_or_create_oauth_user
from app.services.rate_limit import SlidingWindowRateLimiter


def _new_exam() -> Exam:
    return Exam(
        school="THCS Test",
        grade=8,
        subject="Khoa học tự nhiên",
        exam_type="Giữa học kì I",
        duration_minutes=45,
        school_year="2025-2026",
        total_score=10,
        matrix=[],
        summary={},
        specification=[{"question_id": "q1"}],
        questions=[{"id": "q1", "content": "Câu hỏi"}],
        answer_key=[],
        rubric=[],
        validation={},
        resource_package={},
        review_status={},
    )


def test_nonlocal_environment_rejects_public_secret():
    with pytest.raises(ValidationError, match="SECRET_KEY mặc định"):
        Settings(ENV="staging", SECRET_KEY=INSECURE_DEFAULT_SECRET_KEY, _env_file=None)


def test_postgres_failure_never_replaces_live_factory_with_sqlite(monkeypatch):
    previous_factory = database.get_session_factory()
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://invalid/db")
    monkeypatch.setattr(settings, "ENV", "staging")
    monkeypatch.setattr(settings, "USE_POSTGRES", True)
    monkeypatch.setattr(
        database,
        "_create_session_factory",
        lambda _url: (_ for _ in ()).throw(OSError("unreachable")),
    )

    with pytest.raises(RuntimeError, match="từ chối fallback sang SQLite"):
        database.init_db()

    assert database.get_session_factory() is previous_factory


def test_repeated_database_initialization_reuses_engine_and_factory():
    first_engine = database.init_db()
    first_factory = database.get_session_factory()

    assert database.init_db() is first_engine
    assert database.get_session_factory() is first_factory


def test_oauth_requires_verified_email_and_never_relinks_existing_account():
    SessionLocal = database.get_session_factory()
    suffix = uuid4().hex
    email = f"oauth-hardening-{suffix}@example.test"
    with SessionLocal() as db:
        existing = User(
            email=email,
            password_hash=auth_service.hash_password("local-password"),
            name="Local user",
            role="teacher",
            is_active=True,
        )
        db.add(existing)
        db.commit()
        existing_id = existing.id

        with pytest.raises(HTTPException) as unverified:
            find_or_create_oauth_user(
                db, "google", "google-unverified", f"new-{email}", False, "OAuth user"
            )
        assert unverified.value.status_code == 403

        with pytest.raises(HTTPException) as collision:
            find_or_create_oauth_user(
                db, "google", "google-collision", email, True, "Attacker"
            )
        assert collision.value.status_code == 409
        db.expire_all()
        unchanged = db.get(User, existing_id)
        assert unchanged.oauth_provider is None
        assert unchanged.oauth_id is None
        db.delete(unchanged)
        db.commit()


def test_oauth_create_race_returns_concurrent_identity_instead_of_500():
    concurrent_user = SimpleNamespace(is_active=True)

    class RaceQuery:
        def __init__(self, db):
            self.db = db

        def filter(self, *_conditions):
            return self

        def first(self):
            self.db.first_calls += 1
            return concurrent_user if self.db.first_calls == 3 else None

    class RaceSession:
        first_calls = 0
        rollback_called = False

        def query(self, _model):
            return RaceQuery(self)

        def add(self, _user):
            return None

        def commit(self):
            raise IntegrityError("INSERT users", {}, Exception("unique"))

        def rollback(self):
            self.rollback_called = True

    session = RaceSession()
    resolved = find_or_create_oauth_user(
        session,
        "google",
        "concurrent-google-id",
        "concurrent@example.test",
        True,
        "Concurrent user",
    )

    assert resolved is concurrent_user
    assert session.rollback_called is True


def test_missing_user_still_runs_password_verification(monkeypatch):
    calls: list[tuple[str, str]] = []
    dummy_hash = auth_service._dummy_password_hash()

    class MissingQuery:
        def filter(self, *_args):
            return self

        def first(self):
            return None

    db = SimpleNamespace(query=lambda _model: MissingQuery())
    monkeypatch.setattr(
        auth_service,
        "verify_password",
        lambda plain, hashed: calls.append((plain, hashed)) or False,
    )

    with pytest.raises(HTTPException) as error:
        auth_service.authenticate_user(db, "missing@example.test", "guess")

    assert error.value.status_code == 401
    assert calls == [("guess", dummy_hash)]


def test_dummy_password_hash_is_created_lazily_once(monkeypatch):
    calls = 0

    def fake_hash(_password):
        nonlocal calls
        calls += 1
        return "cached-dummy-hash"

    auth_service._dummy_password_hash.cache_clear()
    monkeypatch.setattr(auth_service.pwd_context, "hash", fake_hash)
    try:
        assert auth_service._dummy_password_hash() == "cached-dummy-hash"
        assert auth_service._dummy_password_hash() == "cached-dummy-hash"
        assert calls == 1
    finally:
        auth_service._dummy_password_hash.cache_clear()


def test_rate_limiter_returns_retry_after():
    limiter = SlidingWindowRateLimiter()
    limiter.check("login", limit=1, window_seconds=60)
    with pytest.raises(HTTPException) as limited:
        limiter.check("login", limit=1, window_seconds=60)
    assert limited.value.status_code == 429
    assert int(limited.value.headers["Retry-After"]) >= 1


def test_rate_limiter_prunes_expired_keys(monkeypatch):
    timestamps = iter([0.0, 2.0])
    monkeypatch.setattr(rate_limit_module, "monotonic", lambda: next(timestamps))
    limiter = SlidingWindowRateLimiter()

    limiter.check("expired", limit=2, window_seconds=1)
    limiter.check("active", limit=2, window_seconds=1)

    assert limiter.active_key_count() == 1


def test_login_rate_limit_applies_across_rotating_emails(monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ATTEMPTS", 2)
    client = TestClient(app)

    for index in range(2):
        response = client.post(
            "/api/auth/login",
            json={"email": f"missing-{index}@example.test", "password": "wrong"},
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/auth/login",
        json={"email": "third-address@example.test", "password": "wrong"},
    )
    assert limited.status_code == 429


def test_logout_revokes_the_presented_token(auth_context):
    client = TestClient(app)

    logged_out = client.post("/api/auth/logout", headers=auth_context["headers"])
    assert logged_out.status_code == 204
    assert client.get("/api/auth/me", headers=auth_context["headers"]).status_code == 401


def test_registration_rejects_malformed_email():
    response = TestClient(app).post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "password", "name": "Teacher"},
    )

    assert response.status_code == 422


def test_teacher_creation_rejects_malformed_email(admin_auth_context):
    response = TestClient(app).post(
        "/api/admin/teachers",
        json={"email": "not-an-email", "password": "password", "name": "Teacher"},
        headers=admin_auth_context["headers"],
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_exam_lock_entry_is_removed_after_last_user():
    exam_id = 987_654
    async with exam_service_module._exam_lock(exam_id):
        assert exam_id in exam_service_module._exam_locks

    assert exam_id not in exam_service_module._exam_locks


def test_school_admin_cannot_mutate_global_provider(admin_auth_context):
    response = TestClient(app).post(
        "/api/ai/active",
        json={"provider": "gemini"},
        headers=admin_auth_context["headers"],
    )
    assert response.status_code == 403


def test_curriculum_requires_authentication():
    response = TestClient(app).get("/api/curriculum/grades")
    assert response.status_code == 401


def _signed_token_with_subject(subject) -> str:
    return auth_service.jwt.encode(
        {
            "sub": subject,
            "role": "teacher",
            "ver": 0,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def test_required_auth_rejects_nonnumeric_token_subject():
    response = TestClient(app).get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {_signed_token_with_subject('not-a-user-id')}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token không hợp lệ"


@pytest.mark.parametrize("subject", ["not-a-user-id", None, -1, 0])
def test_optional_auth_treats_invalid_token_subject_as_anonymous(subject):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=_signed_token_with_subject(subject),
    )
    db = SimpleNamespace(
        query=lambda _model: pytest.fail("invalid subjects must not query the database")
    )

    assert auth_service.get_optional_user(credentials, db) is None


@pytest.mark.asyncio
async def test_document_parse_runs_outside_event_loop(monkeypatch, auth_context):
    callback_ran = False

    def slow_save(**_kwargs):
        time.sleep(0.05)
        return {"id": 1}

    def mark_callback():
        nonlocal callback_ran
        callback_ran = True

    monkeypatch.setattr(document_routes.document_service, "save_document", slow_save)
    asyncio.get_running_loop().call_later(0.01, mark_callback)
    upload = UploadFile(filename="document.pdf", file=BytesIO(b"small"))
    await document_routes.upload_document(
        upload,
        grade=8,
        user=auth_context["user"],
    )
    assert callback_ran is True


@pytest.mark.asyncio
async def test_pdf_export_runs_outside_event_loop(monkeypatch):
    service = ExamService()
    callback_ran = False

    def slow_render(_exam_id, _actor, *_export_options):
        time.sleep(0.05)
        return b"pdf"

    def mark_callback():
        nonlocal callback_ran
        callback_ran = True

    monkeypatch.setattr(service, "_render_pdf", slow_render)
    asyncio.get_running_loop().call_later(0.01, mark_callback)
    response = await service.export_pdf(1)
    assert response.media_type == "application/pdf"
    assert callback_ran is True


@pytest.mark.asyncio
async def test_answer_generation_closes_db_session_before_provider_await(monkeypatch):
    service = ExamService()
    real_factory = service.SessionLocal
    with real_factory() as db:
        exam = _new_exam()
        db.add(exam)
        db.commit()
        exam_id = exam.id

    active_sessions = 0

    class TrackedSession:
        def __init__(self):
            self.session = real_factory()

        def __enter__(self):
            nonlocal active_sessions
            active_sessions += 1
            return self.session

        def __exit__(self, exc_type, exc, traceback):
            nonlocal active_sessions
            try:
                self.session.close()
            finally:
                active_sessions -= 1

    monkeypatch.setattr(service, "SessionLocal", lambda: TrackedSession())

    async def generate(**_kwargs):
        assert active_sessions == 0
        return {
            "answer_key": [{"question_id": "q1", "answer": "A"}],
            "rubric": [],
        }

    monkeypatch.setattr(service.answer_agent, "run", generate)
    try:
        await service.generate_answers(
            SimpleNamespace(exam_id=exam_id, accepted_question_ids=["q1"])
        )
    finally:
        with real_factory() as db:
            stored = db.get(Exam, exam_id)
            if stored:
                db.delete(stored)
                db.commit()


def test_exam_json_updates_detect_stale_writes():
    SessionLocal = database.get_session_factory()
    with SessionLocal() as setup:
        exam = _new_exam()
        setup.add(exam)
        setup.commit()
        exam_id = exam.id

    first = SessionLocal()
    second = SessionLocal()
    try:
        first_exam = first.get(Exam, exam_id)
        second_exam = second.get(Exam, exam_id)
        first_exam.review_status = {"q1": {"status": "accepted"}}
        first.commit()
        second_exam.review_status = {"q1": {"status": "rejected"}}
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()
    finally:
        first.close()
        second.close()
        with SessionLocal() as cleanup:
            stored = cleanup.get(Exam, exam_id)
            if stored:
                cleanup.delete(stored)
                cleanup.commit()
