"""Integration proof for super-admin, school-admin, teacher, and viewer scope."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes import ai as ai_routes
from app.core.config import settings
from app.core.database import get_session_factory
from app.main import app
from app.models.school import School
from app.models.user import User
from app.services.auth_service import create_access_token, hash_password


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


class _ConfiguredProvider:
    def available(self) -> bool:
        return True


def test_hierarchical_role_boundaries(monkeypatch):
    suffix = uuid4().hex
    emails = {role: f"{role}-{suffix}@example.test" for role in (
        "super", "other_super", "admin_a", "admin_b", "teacher_a", "teacher_b", "viewer_a"
    )}
    created_email = f"created-{suffix}@example.com"

    with get_session_factory()() as db:
        school_a = School(name=f"School A {suffix}")
        school_b = School(name=f"School B {suffix}")
        db.add_all([school_a, school_b])
        db.flush()
        users = {
            "super": User(email=emails["super"], name="Super", role="super_admin", is_active=True, password_hash=hash_password("password")),
            "other_super": User(email=emails["other_super"], name="Other super", role="super_admin", is_active=True, password_hash=hash_password("password")),
            "admin_a": User(email=emails["admin_a"], name="Admin A", role="school_admin", school_id=school_a.id, is_active=True, password_hash=hash_password("password")),
            "admin_b": User(email=emails["admin_b"], name="Admin B", role="school_admin", school_id=school_b.id, is_active=True, password_hash=hash_password("password")),
            "teacher_a": User(email=emails["teacher_a"], name="Teacher A", role="teacher", school_id=school_a.id, is_active=True, password_hash=hash_password("password")),
            "teacher_b": User(email=emails["teacher_b"], name="Teacher B", role="teacher", school_id=school_b.id, is_active=True, password_hash=hash_password("password")),
            "viewer_a": User(email=emails["viewer_a"], name="Viewer A", role="viewer", school_id=school_a.id, is_active=True, password_hash=hash_password("password")),
        }
        db.add_all(users.values())
        db.commit()
        for user in users.values():
            db.refresh(user)
        school_a_id, school_b_id = school_a.id, school_b.id
        ids = {name: user.id for name, user in users.items()}
        headers = {name: _headers(user) for name, user in users.items()}

    client = TestClient(app)
    created_school_id: int | None = None
    original_provider = settings.AI_PROVIDER
    monkeypatch.setattr(ai_routes, "_get_service", lambda provider: (_ConfiguredProvider(), "test-model"))
    try:
        # Provider metadata and mutation are both restricted to Super Admin.
        for role in ("teacher_a", "admin_a", "viewer_a"):
            assert client.get("/api/ai/status", headers=headers[role]).status_code == 403
            assert client.get("/api/ai/providers", headers=headers[role]).status_code == 403
            assert client.get("/api/ai/models", headers=headers[role]).status_code == 403
        assert client.get("/api/ai/status", headers=headers["super"]).status_code == 200
        assert client.get("/api/ai/providers", headers=headers["super"]).status_code == 200
        assert client.get("/api/ai/models", headers=headers["super"]).status_code == 200
        switched = client.post("/api/ai/active", json={"provider": "gemini"}, headers=headers["teacher_a"])
        assert switched.status_code == 403
        assert client.post(
            "/api/ai/active", json={"provider": "gemini"}, headers=headers["admin_a"]
        ).status_code == 403
        switched = client.post(
            "/api/ai/active", json={"provider": "gemini"}, headers=headers["super"]
        )
        assert switched.status_code == 409
        assert "OpenAI chính" in switched.json()["detail"]
        fixed_primary = client.post(
            "/api/ai/active", json={"provider": "openai"}, headers=headers["super"]
        )
        assert fixed_primary.status_code == 200
        assert fixed_primary.json()["provider"] == "openai"
        assert client.post(
            "/api/ai/model",
            json={"provider": "gemini", "model": "forbidden-model"},
            headers=headers["teacher_a"],
        ).status_code == 403
        assert client.post(
            "/api/ai/test-llm", json={"prompt": "forbidden"}, headers=headers["teacher_a"]
        ).status_code == 403

        # Viewer cannot mutate provider-management state either.
        assert client.post("/api/ai/active", json={"provider": "gemini"}, headers=headers["viewer_a"]).status_code == 403

        # School admin sees and mutates only exact Teacher rows in their own school.
        scoped = client.get("/api/admin/teachers", headers=headers["admin_a"])
        assert scoped.status_code == 200
        assert {row["id"] for row in scoped.json()} == {ids["teacher_a"]}
        assert client.put(
            f"/api/admin/teachers/{ids['teacher_a']}", json={"name": "Teacher A updated"}, headers=headers["admin_a"]
        ).status_code == 200
        assert client.put(
            f"/api/admin/teachers/{ids['teacher_b']}", json={"name": "Cross tenant"}, headers=headers["admin_a"]
        ).status_code == 404
        assert client.put(
            f"/api/admin/teachers/{ids['admin_b']}", json={"name": "Admin target"}, headers=headers["admin_a"]
        ).status_code == 404
        assert client.get("/api/admin/users", headers=headers["admin_a"]).status_code == 403
        assert client.get("/api/admin/schools", headers=headers["admin_a"]).status_code == 403
        assert client.post(
            "/api/admin/schools", json={"name": "Forbidden school"}, headers=headers["admin_a"]
        ).status_code == 403

        # Super admin can list and edit the global school/account surface.
        school_rows = client.get("/api/admin/schools", headers=headers["super"])
        assert school_rows.status_code == 200
        assert {school_a_id, school_b_id} <= {row["id"] for row in school_rows.json()}
        account_rows = client.get("/api/admin/users", headers=headers["super"])
        assert account_rows.status_code == 200
        assert set(ids.values()) <= {row["id"] for row in account_rows.json()}

        created_account = client.post(
            "/api/admin/users",
            json={
                "email": created_email,
                "password": "new-password",
                "name": "Created globally",
                "role": "teacher",
                "school_id": school_b_id,
            },
            headers=headers["super"],
        )
        assert created_account.status_code == 200
        assert created_account.json()["school_id"] == school_b_id

        created = client.post(
            "/api/admin/schools",
            json={"name": f"School C {suffix}", "address": "Initial"},
            headers=headers["super"],
        )
        assert created.status_code == 200
        created_school_id = created.json()["id"]
        edited = client.put(
            f"/api/admin/schools/{created_school_id}",
            json={"name": f"School C updated {suffix}", "address": "Updated"},
            headers=headers["super"],
        )
        assert edited.status_code == 200
        assert edited.json()["address"] == "Updated"

        managed = client.put(
            f"/api/admin/users/{ids['teacher_b']}",
            json={"role": "school_admin", "school_id": school_a_id, "name": "Managed globally", "is_active": True},
            headers=headers["super"],
        )
        assert managed.status_code == 200
        assert managed.json()["role"] == "school_admin"
        assert managed.json()["school_id"] == school_a_id

        missing_school = client.put(
            f"/api/admin/users/{ids['teacher_a']}",
            json={"role": "school_admin", "school_id": None},
            headers=headers["super"],
        )
        assert missing_school.status_code == 400
        protected = client.put(
            f"/api/admin/users/{ids['other_super']}",
            json={"role": "teacher", "school_id": school_a_id},
            headers=headers["super"],
        )
        assert protected.status_code == 403

        with get_session_factory()() as db:
            assert db.get(User, ids["super"]).school_id is None
    finally:
        settings.AI_PROVIDER = original_provider
        with get_session_factory()() as db:
            db.query(User).filter(User.email.in_([*emails.values(), created_email])).delete(synchronize_session=False)
            school_ids = [school_a_id, school_b_id]
            if created_school_id is not None:
                school_ids.append(created_school_id)
            db.query(School).filter(School.id.in_(school_ids)).delete(synchronize_session=False)
            db.commit()
