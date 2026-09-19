"""Sharing authorization and moderation against an isolated database."""

from io import BytesIO
from types import SimpleNamespace

import pytest
from docx import Document
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.api.routes import documents as routes
from app.core.database import Base, _migrate_compatibility_columns
from app.main import app
from app.models.audit_log import AuditLog
from app.models.document import UploadedDocument
from app.models.school import School
from app.models.user import User
from app.schemas.document import DocumentReviewRequest, DocumentSharingRequest
from app.services.auth_service import get_current_user
from app.services.document_service import DocumentService
from app.services.knowledge_base_service import KnowledgeBaseService


@pytest.fixture
def sharing(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'sharing.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        schools = [School(name="School A"), School(name="School B")]
        db.add_all(schools)
        db.flush()
        roles = {
            "owner": ("teacher", schools[0].id), "peer": ("teacher", schools[0].id),
            "other": ("teacher", schools[1].id), "school_admin": ("school_admin", schools[0].id),
            "other_admin": ("school_admin", schools[1].id), "viewer": ("viewer", schools[0].id),
            "unassigned": ("teacher", None), "super": ("super_admin", None),
        }
        users = {name: User(email=f"{name}@sharing.test", name=name, role=role, school_id=school_id,
                            is_active=True, email_verified=True) for name, (role, school_id) in roles.items()}
        db.add_all(users.values())
        db.commit()
    service = DocumentService()
    service.SessionLocal = sessions
    service.upload_dir = tmp_path
    file = Document()
    file.add_paragraph("Tế bào là đơn vị cấu trúc của cơ thể sống. PRIVATE_CONTENT_SENTINEL")
    buffer = BytesIO()
    file.save(buffer)
    doc = service.save_document(filename="shared.docx", data=buffer.getvalue(), grade=8, actor=users["owner"])
    monkeypatch.setattr(routes, "document_service", service)
    yield SimpleNamespace(service=service, users=users, doc=doc, sessions=sessions, engine=engine)
    engine.dispose()


def change(ctx, scope, *, doc=None, actor="owner"):
    doc = doc or ctx.service.get_document(ctx.doc.id, actor=ctx.users[actor])
    return ctx.service.update_sharing(doc.id, DocumentSharingRequest(scope=scope, version_id=doc.version_id), actor=ctx.users[actor])


def moderate(ctx, decision, *, doc=None, actor="super", note=""):
    doc = doc or ctx.service.get_document(ctx.doc.id, actor=ctx.users[actor])
    return ctx.service.review_sharing(doc.id, DocumentReviewRequest(decision=decision, version_id=doc.version_id, note=note), actor=ctx.users[actor])


def assert_read(ctx, actor, allowed):
    user = ctx.users[actor]
    assert (ctx.doc.id in {d.id for d in ctx.service.list_documents(actor=user)}) == allowed
    if allowed:
        assert ctx.service.get_document(ctx.doc.id, actor=user).id == ctx.doc.id
        assert ctx.service.get_documents_for_rag([ctx.doc.id], actor=user)[0].id == ctx.doc.id
    else:
        for call in (
            lambda: ctx.service.get_document(ctx.doc.id, actor=user),
            lambda: ctx.service.get_documents_for_rag([ctx.doc.id], actor=user),
        ):
            with pytest.raises(HTTPException) as error:
                call()
            assert error.value.status_code == 404


def test_private_defaults_preserve_owner_and_admin_oversight(sharing):
    assert sharing.doc.sharing_scope == "private" and sharing.doc.sharing_status == "none"
    assert sharing.doc.can_manage and sharing.doc.can_share_school
    for actor in sharing.users:
        assert_read(sharing, actor, actor in {"owner", "school_admin", "super"})


def test_school_sharing_is_read_only_and_school_bound(sharing):
    change(sharing, "school")
    for actor in sharing.users:
        assert_read(sharing, actor, actor in {"owner", "peer", "school_admin", "viewer", "super"})
    for actor in ("peer", "school_admin", "viewer", "other"):
        with pytest.raises(HTTPException):
            change(sharing, "private", actor=actor)
        with pytest.raises(HTTPException):
            sharing.service.delete_document(sharing.doc.id, actor=sharing.users[actor])
    assert len(sharing.service.list_documents(actor=sharing.users["peer"], library="school")) == 1
    assert sharing.service.list_documents(actor=sharing.users["peer"], library="mine") == []
    assert not sharing.service.get_document(sharing.doc.id, actor=sharing.users["peer"]).can_manage


def test_system_requires_approval_and_can_be_withdrawn_by_owner(sharing):
    pending = change(sharing, "system")
    assert pending.sharing_status == "pending"
    for actor in ("peer", "other", "viewer", "unassigned", "other_admin"):
        assert_read(sharing, actor, False)
    assert len(sharing.service.list_documents(actor=sharing.users["super"], library="pending")) == 1
    for actor in ("owner", "peer", "school_admin", "viewer"):
        with pytest.raises(HTTPException) as error:
            sharing.service.list_documents(actor=sharing.users[actor], library="pending")
        assert error.value.status_code == 403
        with pytest.raises(HTTPException) as error:
            moderate(sharing, "approve", doc=pending, actor=actor)
        assert error.value.status_code == 403
    approved = moderate(sharing, "approve", doc=pending)
    assert approved.sharing_status == "approved"
    for actor in sharing.users:
        assert_read(sharing, actor, True)
    assert len(sharing.service.list_documents(actor=sharing.users["other"], library="system")) == 1
    change(sharing, "private", doc=approved)
    assert_read(sharing, "other", False)
    assert sharing.service.list_documents(actor=sharing.users["other"], library="system") == []


def test_rejection_resubmission_and_admin_withdrawal(sharing):
    change(sharing, "system")
    rejected = moderate(sharing, "reject", note="Cần kiểm tra nguồn")
    assert rejected.sharing_status == "rejected"
    assert sharing.service.get_document(sharing.doc.id, actor=sharing.users["owner"]).review_note == "Cần kiểm tra nguồn"
    assert_read(sharing, "peer", False)
    pending = change(sharing, "system")
    assert pending.sharing_status == "pending" and pending.review_note == ""
    moderate(sharing, "approve")
    assert_read(sharing, "other", True)
    moderate(sharing, "reject", note="Thu hồi duyệt")
    assert_read(sharing, "other", False)


def test_stale_approval_cannot_republish_revoked_request(sharing):
    pending = change(sharing, "system")
    withdrawn = change(sharing, "private")
    with pytest.raises(HTTPException) as error:
        moderate(sharing, "approve", doc=pending)
    assert error.value.status_code == 409
    assert sharing.service.get_document(sharing.doc.id, actor=sharing.users["owner"]).version_id == withdrawn.version_id
    with sharing.sessions() as db:
        events = db.query(AuditLog).all()
        assert [event.action for event in events] == ["document.sharing_changed", "document.sharing_changed"]
        assert all("PRIVATE_CONTENT_SENTINEL" not in str(event.details) for event in events)


def test_optimistic_commit_rejects_concurrent_moderator_snapshot(sharing):
    change(sharing, "system")
    with sharing.sessions() as stale:
        document = stale.get(UploadedDocument, sharing.doc.id)
        change(sharing, "private")
        document.sharing_status = "approved"
        with pytest.raises(HTTPException) as error:
            sharing.service._commit_sharing(stale)
        assert error.value.status_code == 409
    assert_read(sharing, "other", False)


def test_revocation_excludes_documents_from_next_rag_retrieval(sharing):
    change(sharing, "school")
    kb = KnowledgeBaseService()
    kb.document_service = sharing.service
    chunks = kb._chunks(grade=None, document_ids=[sharing.doc.id], actor=sharing.users["peer"])
    assert chunks and all(c["metadata"]["doc_id"] == sharing.doc.id for c in chunks)
    change(sharing, "private")
    with pytest.raises(HTTPException) as error:
        kb._chunks(grade=None, document_ids=[sharing.doc.id], actor=sharing.users["peer"])
    assert error.value.status_code == 404


def test_schoolless_or_transferred_owner_cannot_share_into_a_school(sharing):
    sharing.users["owner"].school_id = None
    with pytest.raises(HTTPException) as error:
        change(sharing, "school")
    assert error.value.status_code == 400
    sharing.users["owner"].school_id = sharing.users["other"].school_id
    with pytest.raises(HTTPException) as error:
        change(sharing, "school")
    assert error.value.status_code == 400
    change(sharing, "system")  # Global requests do not require a school.


def test_http_contract_enforces_writes_and_rejects_approval_injection(sharing):
    current = [sharing.users["owner"]]
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = lambda: current[0]
    client = TestClient(app)
    url = f"/api/documents/{sharing.doc.id}"
    try:
        assert client.patch(url + "/sharing", json={"scope": "system", "version_id": 1, "sharing_status": "approved"}).status_code == 422
        pending = client.patch(url + "/sharing", json={"scope": "system", "version_id": 1})
        assert pending.status_code == 200 and pending.json()["sharing_status"] == "pending"
        assert client.post(url + "/review", json={"decision": "approve", "version_id": 2}).status_code == 403
        current[0] = sharing.users["super"]
        assert client.get("/api/documents?library=pending").json()[0]["id"] == sharing.doc.id
        assert client.post(url + "/review", json={"decision": "approve", "version_id": 2}).status_code == 200
        current[0] = sharing.users["other"]
        assert client.get(url).status_code == 200
        assert client.get("/api/documents?library=system&grade=8").json()[0]["id"] == sharing.doc.id
        assert client.delete(url).status_code == 404
        assert client.patch(url + "/sharing", json={"scope": "private", "version_id": 3}).status_code == 404
        current[0] = sharing.users["viewer"]
        assert client.patch(url + "/sharing", json={"scope": "private", "version_id": 3}).status_code == 403
        assert client.delete(url).status_code == 403
        assert client.get("/api/documents?library=pending").status_code == 403
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_legacy_migration_keeps_data_private_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE uploaded_documents (id INTEGER PRIMARY KEY, filename TEXT, extracted_text TEXT, owner_user_id INTEGER, school_id INTEGER)"))
        connection.execute(text("INSERT INTO uploaded_documents VALUES (1, 'old.pdf', 'original text', 13, 2)"))
    _migrate_compatibility_columns(engine)
    _migrate_compatibility_columns(engine)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT * FROM uploaded_documents")).mappings().one()
        assert row["extracted_text"] == "original text" and row["owner_user_id"] == 13
        assert row["sharing_scope"] == "private" and row["sharing_status"] == "none" and row["version_id"] == 1
        assert row["reviewed_at"] is None and row["review_note"] == ""
    assert "ix_uploaded_documents_sharing_scope" in {i["name"] for i in inspect(engine).get_indexes("uploaded_documents")}
    engine.dispose()
