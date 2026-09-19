from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.core.database import get_session_factory
from app.main import app
from app.models.user import User
from app.services.auth_service import create_access_token, hash_password


@pytest.fixture
def super_admin_auth_context():
    with get_session_factory()() as db:
        user = User(
            email=f"codex-super-admin-{uuid4().hex}@example.test",
            password_hash=hash_password("not-used-in-test"),
            name="Codex Test Super Admin",
            role="super_admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        context = {
            "headers": {
                "Authorization": f"Bearer {create_access_token(user.id, user.role)}"
            }
        }
        yield context
        db.delete(user)
        db.commit()


def test_ai_status_never_exposes_api_keys(super_admin_auth_context):
    response = TestClient(app).get(
        "/api/ai/status", headers=super_admin_auth_context["headers"]
    )

    assert response.status_code == 200
    data = response.json()
    assert {"provider", "model", "verify_model", "configured", "key_exposed"} <= data.keys()
    assert data["key_exposed"] is False
    assert all("key" not in key.lower() or key == "key_exposed" for key in data)


def test_ai_admin_actions_require_authentication():
    response = TestClient(app).post("/api/ai/active", json={"provider": "gemini"})
    assert response.status_code == 401


def test_ai_status_rejects_teachers(auth_context):
    response = TestClient(app).get("/api/ai/status", headers=auth_context["headers"])
    assert response.status_code == 403


def test_provider_metadata_exposes_only_fixed_order(super_admin_auth_context):
    response = TestClient(app).get(
        "/api/ai/providers", headers=super_admin_auth_context["headers"]
    )

    assert response.status_code == 200
    data = response.json()
    assert data["active_provider"] == "openai"
    assert [item["provider"] for item in data["providers"]] == [
        "openai",
        "gemini",
        "deepseek",
    ]
    assert [item["priority"] for item in data["providers"]] == [1, 2, 3]
    assert [item["role"] for item in data["providers"]] == [
        "primary",
        "fallback",
        "fallback",
    ]


def test_school_admin_cannot_mutate_provider_chain(admin_auth_context):
    response = TestClient(app).post(
        "/api/ai/active",
        headers=admin_auth_context["headers"],
        json={"provider": "gemini"},
    )

    assert response.status_code == 403


def test_school_admin_cannot_view_provider_metadata(admin_auth_context):
    client = TestClient(app)

    assert client.get(
        "/api/ai/status", headers=admin_auth_context["headers"]
    ).status_code == 403
    assert client.get(
        "/api/ai/providers", headers=admin_auth_context["headers"]
    ).status_code == 403
    assert client.get(
        "/api/ai/models", headers=admin_auth_context["headers"]
    ).status_code == 403
