"""Account self-service and password-capability regression proof."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_session_factory
from app.main import app
from app.models.school import School
from app.models.user import User
from app.services.auth_service import create_access_token, hash_password, verify_password


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def test_account_profile_school_and_local_password_flow():
    suffix = uuid4().hex
    email = f"account-{suffix}@example.test"
    original_password = "current-password"

    with get_session_factory()() as db:
        school = School(name=f"THPT Smart {suffix}", address="12 Nguyễn Du", phone="024-1234-5678")
        db.add(school)
        db.flush()
        user = User(
            email=email,
            password_hash=hash_password(original_password),
            name="Tên ban đầu",
            role="teacher",
            is_active=True,
            school_id=school.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        school_id = school.id
        user_id = user.id
        headers = _headers(user)

    client = TestClient(app)
    try:
        me = client.get("/api/auth/me", headers=headers)
        assert me.status_code == 200, me.text
        assert me.json()["can_change_password"] is True

        assigned_school = client.get("/api/admin/school", headers=headers)
        assert assigned_school.status_code == 200, assigned_school.text
        assert assigned_school.json() == {
            "id": school_id,
            "name": f"THPT Smart {suffix}",
            "address": "12 Nguyễn Du",
            "phone": "024-1234-5678",
            "created_at": assigned_school.json()["created_at"],
        }

        profile = client.put("/api/auth/profile", json={"name": "  Nguyễn Văn Mới  "}, headers=headers)
        assert profile.status_code == 200, profile.text
        assert profile.json()["name"] == "Nguyễn Văn Mới"
        assert profile.json()["school_id"] == school_id

        forbidden_membership_change = client.put(
            "/api/auth/profile",
            json={"name": "Nguyễn Văn Mới", "school": "Trường tự chọn"},
            headers=headers,
        )
        assert forbidden_membership_change.status_code == 422

        wrong_current = client.post(
            "/api/auth/change-password",
            json={"current_password": "wrong-password", "new_password": "new-password"},
            headers=headers,
        )
        assert wrong_current.status_code == 400

        reused = client.post(
            "/api/auth/change-password",
            json={"current_password": original_password, "new_password": original_password},
            headers=headers,
        )
        assert reused.status_code == 400
        assert reused.json()["detail"] == "Mật khẩu mới phải khác mật khẩu hiện tại"
        assert client.get("/api/auth/me", headers=headers).status_code == 200

        changed = client.post(
            "/api/auth/change-password",
            json={"current_password": original_password, "new_password": "new-password"},
            headers=headers,
        )
        assert changed.status_code == 200, changed.text
        replacement_headers = {
            "Authorization": f"Bearer {changed.json()['access_token']}"
        }

        revoked = client.get("/api/auth/me", headers=headers)
        assert revoked.status_code == 401
        assert revoked.json()["detail"] == "Phiên đăng nhập đã bị thu hồi"
        assert client.get("/api/auth/me", headers=replacement_headers).status_code == 200

        with get_session_factory()() as db:
            updated = db.get(User, user_id)
            assert updated is not None
            assert verify_password("new-password", updated.password_hash)
            assert updated.school_id == school_id
    finally:
        with get_session_factory()() as db:
            db.query(User).filter(User.email == email).delete(synchronize_session=False)
            db.query(School).filter(School.id == school_id).delete(synchronize_session=False)
            db.commit()


def test_oauth_only_account_cannot_change_local_password():
    suffix = uuid4().hex
    email = f"oauth-account-{suffix}@example.test"

    with get_session_factory()() as db:
        user = User(
            email=email,
            password_hash=None,
            name="OAuth Teacher",
            role="teacher",
            is_active=True,
            oauth_provider="google",
            oauth_id=suffix,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        headers = _headers(user)

    client = TestClient(app)
    try:
        me = client.get("/api/auth/me", headers=headers)
        assert me.status_code == 200, me.text
        assert me.json()["can_change_password"] is False

        changed = client.post(
            "/api/auth/change-password",
            json={"current_password": "unused-password", "new_password": "new-password"},
            headers=headers,
        )
        assert changed.status_code == 400
        assert changed.json()["detail"] == "Tài khoản OAuth không thể đổi mật khẩu"
    finally:
        with get_session_factory()() as db:
            db.query(User).filter(User.email == email).delete(synchronize_session=False)
            db.commit()
