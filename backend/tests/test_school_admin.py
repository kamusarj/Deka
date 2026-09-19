"""Regression tests for school membership administration."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_session_factory
from app.main import app
from app.models.school import School
from app.models.user import User
from app.services.auth_service import create_access_token, hash_password


def test_school_admin_can_attach_and_detach_only_unassigned_teachers():
    suffix = uuid4().hex
    admin_email = f"admin-{suffix}@example.com"
    free_email = f"free-{suffix}@example.com"
    other_email = f"other-{suffix}@example.com"

    with get_session_factory()() as db:
        school = School(name=f"School {suffix}")
        other_school = School(name=f"Other school {suffix}")
        db.add_all([school, other_school])
        db.flush()
        admin = User(
            email=admin_email, name="Admin", role="school_admin", school_id=school.id,
            is_active=True, password_hash=hash_password("test-password"),
        )
        free_teacher = User(
            email=free_email, name="Free teacher", role="teacher", school_id=None,
            is_active=True, password_hash=hash_password("test-password"),
        )
        other_teacher = User(
            email=other_email, name="Other teacher", role="teacher", school_id=other_school.id,
            is_active=True, password_hash=hash_password("test-password"),
        )
        db.add_all([admin, free_teacher, other_teacher])
        db.commit()
        db.refresh(free_teacher)
        free_teacher_id = free_teacher.id
        school_id = school.id
        other_school_id = other_school.id
        headers = {"Authorization": f"Bearer {create_access_token(admin.id, admin.role)}"}

    client = TestClient(app)
    try:
        attached = client.post("/api/admin/teachers/assign", json={"email": free_email}, headers=headers)
        assert attached.status_code == 200, attached.text
        assert attached.json()["school_id"] == school_id

        blocked_transfer = client.post("/api/admin/teachers/assign", json={"email": other_email}, headers=headers)
        assert blocked_transfer.status_code == 409

        removed = client.delete(f"/api/admin/teachers/{free_teacher_id}", headers=headers)
        assert removed.status_code == 200
        assert removed.json() == {"id": free_teacher_id, "removed": True}

        with get_session_factory()() as db:
            retained_teacher = db.get(User, free_teacher_id)
            assert retained_teacher is not None
            assert retained_teacher.school_id is None
    finally:
        with get_session_factory()() as db:
            db.query(User).filter(User.email.in_([admin_email, free_email, other_email])).delete(synchronize_session=False)
            db.query(School).filter(School.id.in_([school_id, other_school_id])).delete(synchronize_session=False)
            db.commit()
