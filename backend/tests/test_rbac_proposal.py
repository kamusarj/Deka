from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.routes import auth as auth_routes
from app.core.database import get_session_factory
from app.main import app
from app.models.account_token import AccountToken
from app.models.exam import Exam
from app.models.school import School
from app.models.user import User
from app.schemas.bank_question import BankQuestionCreate
from app.services.auth_service import create_access_token, hash_password
from app.services.question_bank_service import QuestionBankService
from app.services.rate_limit import login_limiter


def _headers(user) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(user.id, user.role, user.token_version)}"
    }


def test_registration_verification_and_reset_tokens_are_one_use(monkeypatch):
    login_limiter.clear()
    sent_urls: list[str] = []
    monkeypatch.setattr(
        auth_routes,
        "send_account_email",
        lambda **kwargs: sent_urls.append(kwargs["action_url"]),
    )
    email = f"lifecycle-{uuid4().hex}@example.com"
    client = TestClient(app)

    registered = client.post(
        "/api/auth/register",
        json={"email": email, "password": "initial-password", "name": "Lifecycle"},
    )
    assert registered.status_code == 201
    assert registered.json()["requires_email_verification"] is True
    assert client.post(
        "/api/auth/login", json={"email": email, "password": "initial-password"}
    ).status_code == 403

    verify_token = sent_urls[-1].split("token=", 1)[1]
    with get_session_factory()() as db:
        stored = db.query(AccountToken).filter(AccountToken.purpose == "verify_email").order_by(
            AccountToken.id.desc()
        ).first()
        assert stored is not None
        assert verify_token != stored.token_hash

    assert client.post("/api/auth/verify-email", json={"token": verify_token}).status_code == 200
    assert client.post("/api/auth/verify-email", json={"token": verify_token}).status_code == 400
    assert client.post(
        "/api/auth/login", json={"email": email, "password": "initial-password"}
    ).status_code == 200

    login_limiter.clear()
    forgot = client.post("/api/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    reset_token = sent_urls[-1].split("token=", 1)[1]
    assert client.post(
        "/api/auth/reset-password",
        json={"token": reset_token, "new_password": "replacement-password"},
    ).status_code == 200
    assert client.post(
        "/api/auth/reset-password",
        json={"token": reset_token, "new_password": "another-password"},
    ).status_code == 400


def test_viewer_is_read_only_and_school_admin_mutates_only_owned_rows():
    suffix = uuid4().hex
    with get_session_factory()() as db:
        school = School(name=f"RBAC {suffix}")
        db.add(school)
        db.flush()
        owner = User(
            email=f"owner-{suffix}@example.com", name="Owner", role="teacher",
            school_id=school.id, is_active=True, password_hash=hash_password("password"),
        )
        admin = User(
            email=f"admin-{suffix}@example.com", name="Admin", role="school_admin",
            school_id=school.id, is_active=True, password_hash=hash_password("password"),
        )
        viewer = User(
            email=f"viewer-{suffix}@example.com", name="Viewer", role="viewer",
            school_id=school.id, is_active=True, password_hash=hash_password("password"),
        )
        db.add_all([owner, admin, viewer])
        db.commit()
        for user in (owner, admin, viewer):
            db.refresh(user)
        actors = {
            "owner": SimpleNamespace(id=owner.id, role=owner.role, school_id=owner.school_id),
            "admin": SimpleNamespace(id=admin.id, role=admin.role, school_id=admin.school_id),
            "super": SimpleNamespace(id=-1, role="super_admin", school_id=None),
        }
        viewer_headers = _headers(viewer)

    payload = BankQuestionCreate(content="Scoped question", type="short_answer")
    service = QuestionBankService()
    question = service.add_question(payload, actor=actors["owner"])
    assert any(row.id == question.id for row in service.list_questions(actor=actors["admin"]))
    with pytest.raises(HTTPException) as denied:
        service.delete_question(question.id, actor=actors["admin"])
    assert denied.value.status_code == 404

    response = TestClient(app).post(
        "/api/question-bank",
        headers=viewer_headers,
        json={"content": "Viewer write", "type": "short_answer"},
    )
    assert response.status_code == 403
    service.delete_question(question.id, actor=actors["super"])


def test_admin_created_account_must_change_temporary_password():
    suffix = uuid4().hex
    with get_session_factory()() as db:
        admin = User(
            email=f"super-{suffix}@example.com", name="Super", role="super_admin",
            is_active=True, password_hash=hash_password("password"),
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        headers = _headers(admin)

    client = TestClient(app)
    created = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "email": f"managed-{suffix}@example.com",
            "password": "temporary-password",
            "name": "Managed",
            "role": "viewer",
            "school_id": None,
        },
    )
    assert created.status_code == 200
    assert created.json()["must_change_password"] is True

    login_limiter.clear()
    login = client.post(
        "/api/auth/login",
        json={"email": created.json()["email"], "password": "temporary-password"},
    )
    assert login.status_code == 200
    managed_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/exams", headers=managed_headers).status_code == 403
    assert client.get("/api/auth/me", headers=managed_headers).status_code == 200


def _exam(*, owner_id: int, school_id: int, subject: str, question_count: int = 1) -> Exam:
    return Exam(
        owner_user_id=owner_id,
        school_id=school_id,
        school="Scoped School",
        grade=8,
        subject=subject,
        exam_type="Giữa học kì I",
        duration_minutes=45,
        school_year="2026-2027",
        total_score=10,
        matrix=[],
        summary={"total_questions": question_count, "total_score": 10},
        specification=[],
        questions=[{"id": f"q-{index}"} for index in range(question_count)],
        answer_key=[],
        rubric=[],
        validation={},
        review_status={},
    )


def test_dashboard_and_exam_search_follow_actor_scope():
    suffix = uuid4().hex
    with get_session_factory()() as db:
        school = School(name=f"Scoped dashboard {suffix}")
        db.add(school)
        db.flush()
        teacher_a = User(
            email=f"dash-a-{suffix}@example.com", name="Teacher A", role="teacher",
            school_id=school.id, is_active=True, password_hash=hash_password("password"),
        )
        teacher_b = User(
            email=f"dash-b-{suffix}@example.com", name="Teacher B", role="teacher",
            school_id=school.id, is_active=True, password_hash=hash_password("password"),
        )
        admin = User(
            email=f"dash-admin-{suffix}@example.com", name="Admin", role="school_admin",
            school_id=school.id, is_active=True, password_hash=hash_password("password"),
        )
        db.add_all([teacher_a, teacher_b, admin])
        db.flush()
        db.add_all([
            _exam(owner_id=teacher_a.id, school_id=school.id, subject="Vật lý", question_count=2),
            _exam(owner_id=teacher_b.id, school_id=school.id, subject="Hóa học", question_count=3),
        ])
        db.commit()
        for user in (teacher_a, admin):
            db.refresh(user)
        teacher_headers = _headers(teacher_a)
        admin_headers = _headers(admin)

    client = TestClient(app)
    teacher_page = client.get("/api/exams/search", headers=teacher_headers)
    assert teacher_page.status_code == 200
    assert teacher_page.json()["total"] == 1
    assert teacher_page.json()["items"][0]["owner_name"] == "Teacher A"
    admin_page = client.get(
        "/api/exams/search", headers=admin_headers, params={"subject": "Hóa", "page_size": 1}
    )
    assert admin_page.status_code == 200
    assert admin_page.json()["total"] == 1
    assert admin_page.json()["items"][0]["owner_name"] == "Teacher B"
    teacher_summary = client.get("/api/dashboard/summary", headers=teacher_headers).json()
    admin_summary = client.get("/api/dashboard/summary", headers=admin_headers).json()
    assert (teacher_summary["exams"], teacher_summary["questions"]) == (1, 2)
    assert (admin_summary["exams"], admin_summary["questions"]) == (2, 5)


def test_transfer_soft_delete_school_delete_and_audit_are_explicit():
    suffix = uuid4().hex
    with get_session_factory()() as db:
        source = School(name=f"Source {suffix}")
        target = School(name=f"Target {suffix}")
        empty = School(name=f"Empty {suffix}")
        db.add_all([source, target, empty])
        db.flush()
        super_admin = User(
            email=f"audit-super-{suffix}@example.com", name="Super", role="super_admin",
            is_active=True, password_hash=hash_password("password"),
        )
        teacher = User(
            email=f"transfer-{suffix}@example.com", name="Transfer", role="teacher",
            school_id=source.id, is_active=True, password_hash=hash_password("password"),
        )
        db.add_all([super_admin, teacher])
        db.commit()
        for row in (super_admin, teacher, source, target, empty):
            db.refresh(row)
        headers = _headers(super_admin)
        ids = {"teacher": teacher.id, "source": source.id, "target": target.id, "empty": empty.id}

    client = TestClient(app)
    transfer = client.post(
        f"/api/admin/teachers/{ids['teacher']}/transfer",
        headers=headers,
        json={"school_id": ids["target"]},
    )
    assert transfer.status_code == 200
    assert transfer.json()["school_id"] == ids["target"]
    assert client.delete(f"/api/admin/schools/{ids['target']}", headers=headers).status_code == 409
    assert client.delete(f"/api/admin/users/{ids['teacher']}", headers=headers).status_code == 200
    # Soft-deleted accounts retain attribution and therefore still block school deletion.
    assert client.delete(f"/api/admin/schools/{ids['target']}", headers=headers).status_code == 409
    assert client.delete(f"/api/admin/schools/{ids['empty']}", headers=headers).status_code == 200
    actions = {
        item["action"]
        for item in client.get("/api/admin/audit-logs", headers=headers).json()["items"]
    }
    assert {
        "admin.teacher_transferred",
        "admin.user_soft_deleted",
        "admin.school_deleted",
    } <= actions
