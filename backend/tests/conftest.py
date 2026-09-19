"""Pytest configuration for backend tests."""

import os
from uuid import uuid4

import pytest

# Tests deliberately select the local database. This is explicit test
# configuration, not the runtime Postgres-failure fallback prohibited in US-117.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("USE_POSTGRES", "false")
os.environ.setdefault("SECRET_KEY", "test-suite-secret-key-with-more-than-32-bytes")

from app.core.config import settings
from app.core.database import get_session_factory
from app.models.user import User
from app.services.auth_service import create_access_token, hash_password
from app.services.rate_limit import ai_limiter, login_limiter

pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(autouse=True)
def reset_local_rate_limits():
    login_limiter.clear()
    ai_limiter.clear()
    yield
    login_limiter.clear()
    ai_limiter.clear()


@pytest.fixture(autouse=True)
def disable_external_ai(monkeypatch):
    """Keep the test suite deterministic and prevent use of paid credentials.

    Developers may have provider keys in their ignored ``backend/.env``. Tests
    must never turn those into network calls merely because an agent is created.
    Unit tests that exercise AI behavior explicitly set ``has_ai`` and mock the
    provider response instead.
    """
    for key_name in (
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENAI_COMPATIBLE_API_KEY",
    ):
        monkeypatch.setattr(settings, key_name, "")


@pytest.fixture
def auth_context():
    """Authenticated teacher context for API tests that handle private data."""
    with get_session_factory()() as db:
        user = User(
            email=f"codex-{uuid4().hex}@example.test",
            password_hash=hash_password("not-used-in-test"),
            name="Codex Test Teacher",
            role="teacher",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        context = {
            "user": user,
            "headers": {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"},
        }
        yield context
        db.delete(user)
        db.commit()


@pytest.fixture
def admin_auth_context():
    """Authenticated school-admin context for configuration endpoint tests."""
    with get_session_factory()() as db:
        user = User(
            email=f"codex-admin-{uuid4().hex}@example.test",
            password_hash=hash_password("not-used-in-test"),
            name="Codex Test Admin",
            role="school_admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        context = {
            "user": user,
            "headers": {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"},
        }
        yield context
        db.delete(user)
        db.commit()
