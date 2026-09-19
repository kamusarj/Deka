"""Provisioning proof against an isolated database and ordinary auth routes."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.school import School
from app.models.user import User
from app.services import demo_accounts
from app.services.auth_service import hash_password
from app.services.role_policy import KNOWN_ROLES


@pytest.fixture
def demo_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_cli_requires_explicit_opt_in_before_connecting(monkeypatch):
    def unexpected_connection():
        pytest.fail("must not connect without explicit demo opt-in")

    monkeypatch.setattr(demo_accounts, "get_session_factory", unexpected_connection)
    with pytest.raises(SystemExit) as error:
        demo_accounts.main([])
    assert error.value.code == 2


def test_all_roles_use_real_password_login_and_server_authorization(demo_db):
    result = demo_accounts.seed_demo_accounts(demo_db)
    demo_db.commit()
    assert {account["role"] for account in result} == KNOWN_ROLES
    assert all(account["status"] == "created" for account in result)
    school = demo_db.query(School).one()

    def override_db():
        yield demo_db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        for role, email, _ in demo_accounts.DEMO_ACCOUNTS:
            response = client.post("/api/auth/login", json={
                "email": email, "password": demo_accounts.DEMO_PASSWORD,
            })
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["user"]["role"] == role
            assert payload["user"]["school_id"] == (None if role == "super_admin" else school.id)
            headers = {"Authorization": f"Bearer {payload['access_token']}"}
            me = client.get("/api/auth/me", headers=headers)
            assert me.status_code == 200
            assert me.json()["email"] == email
            schools = client.get("/api/admin/schools", headers=headers)
            assert schools.status_code == (200 if role == "super_admin" else 403)
            if role == "school_admin":
                teachers = client.get("/api/admin/teachers", headers=headers)
                assert teachers.status_code == 200
                assert "teacher@demo.smart-exam.test" in teachers.text
        bad_password = client.post("/api/auth/login", json={
            "email": demo_accounts.DEMO_ACCOUNTS[0][1], "password": "wrong-password",
        })
        assert bad_password.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)

    events = demo_db.query(AuditLog).all()
    assert len(events) == 5
    audit_text = json.dumps([event.details for event in events])
    assert demo_accounts.DEMO_PASSWORD not in audit_text
    assert "password_hash" not in audit_text


def test_repeating_seed_preserves_accounts_and_does_not_duplicate_audits(demo_db):
    demo_accounts.seed_demo_accounts(demo_db)
    demo_db.commit()
    users = demo_db.query(User).order_by(User.id).all()
    users[0].name = "Edited demo display name"
    users[0].token_version = 9
    demo_db.commit()
    before = [(user.id, user.password_hash, user.name, user.token_version) for user in users]

    result = demo_accounts.seed_demo_accounts(demo_db)
    demo_db.commit()

    after = [(user.id, user.password_hash, user.name, user.token_version)
             for user in demo_db.query(User).order_by(User.id).all()]
    assert before == after
    assert all(account["status"] == "reused" for account in result)
    assert demo_db.query(School).count() == 1
    assert demo_db.query(AuditLog).count() == 5


@pytest.mark.parametrize("change", [
    {"role": "super_admin"},
    {"is_active": False},
    {"email_verified": False},
    {"must_change_password": True},
    {"password_hash": None},
])
def test_conflicting_account_is_never_overwritten_or_partially_seeded(demo_db, change):
    school = School(name=demo_accounts.DEMO_SCHOOL_NAME)
    demo_db.add(school)
    demo_db.flush()
    values = dict(
        email="viewer@demo.smart-exam.test", name="Existing account", role="viewer",
        password_hash=hash_password(demo_accounts.DEMO_PASSWORD), school_id=school.id,
        is_active=True, email_verified=True, must_change_password=False,
    )
    values.update(change)
    user = User(**values)
    demo_db.add(user)
    demo_db.commit()
    with pytest.raises(ValueError, match="conflicts with an existing account"):
        with demo_db.begin():
            demo_accounts.seed_demo_accounts(demo_db)
    assert demo_db.query(User).count() == 1
    assert demo_db.query(AuditLog).count() == 0
    demo_db.refresh(user)
    for key, value in change.items():
        assert getattr(user, key) == value


def test_failure_rolls_back_school_users_and_audits(demo_db, monkeypatch):
    def failed_audit(*args, **kwargs):
        raise RuntimeError("audit storage unavailable")

    monkeypatch.setattr(demo_accounts, "record_audit", failed_audit)
    with pytest.raises(RuntimeError, match="audit storage unavailable"):
        with demo_db.begin():
            demo_accounts.seed_demo_accounts(demo_db)
    assert demo_db.query(User).count() == 0
    assert demo_db.query(School).count() == 0
    assert demo_db.query(AuditLog).count() == 0
