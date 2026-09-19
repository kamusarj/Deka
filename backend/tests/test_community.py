"""Community permissions and persistence in an isolated database."""
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from app.api.routes import community as routes
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.bank_question import BankQuestion
from app.models.community import CommunityTopic
from app.models.school import School
from app.models.user import User
from app.schemas.community import CommentCreate, TopicCreate, TopicFromBank
from app.services.auth_service import get_current_user
from app.services.community_service import CommunityService
from app.services.question_bank_service import QuestionBankService

@pytest.fixture
def forum(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'forum.db'}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _): connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        schools = [School(name="A"), School(name="B")]
        db.add_all(schools); db.flush()
        users = {key: User(name=key, email=f"{key}@private.test", role=role, school_id=school, is_active=True) for key, role, school in [
            ("owner", "teacher", schools[0].id), ("other", "teacher", schools[1].id),
            ("admin", "school_admin", schools[0].id), ("super", "super_admin", None),
            ("viewer", "viewer", schools[1].id), ("unknown", "root", None)]}
        db.add_all(users.values()); db.commit()
    service = CommunityService(); service.SessionLocal = sessions
    bank = QuestionBankService(); bank.SessionLocal = sessions
    monkeypatch.setattr(routes, "community_service", service)
    routes.community_limiter.clear()
    app = FastAPI(); app.include_router(routes.router, prefix="/api")
    yield SimpleNamespace(service=service, bank=bank, users=users, sessions=sessions, app=app, engine=engine)
    routes.community_limiter.clear(); engine.dispose()

def topic(ctx, actor="owner", title="Tế bào và sự sống", **question):
    return ctx.service.create_topic(TopicCreate(title=title, question={"content": "Tế bào là gì?", "type": "short_answer", "grade": 6, **question}), actor=ctx.users[actor])

def denied(code, callback):
    with pytest.raises(HTTPException) as error: callback()
    assert error.value.status_code == code

def test_immediate_cross_school_publication_and_member_boundary(forum):
    created = topic(forum)
    for role in ("owner", "other", "viewer", "admin", "super"):
        result = forum.service.list_topics(actor=forum.users[role])
        assert result["total"] == 1 and result["items"][0]["id"] == created["id"]
        assert "question" not in result["items"][0]
        assert "email" not in forum.service.get_topic(created["id"], actor=forum.users[role])["author"]
    topic(forum, actor="viewer")
    denied(403, lambda: forum.service.list_topics(actor=forum.users["unknown"]))
    denied(403, lambda: forum.service.list_topics(actor=None))
    forum.users["other"].is_active = False
    denied(403, lambda: forum.service.list_topics(actor=forum.users["other"]))

def test_bank_share_preserves_private_access_and_strips_provenance(forum):
    with forum.sessions() as db:
        row = BankQuestion(owner_user_id=forum.users["owner"].id, school_id=forum.users["owner"].school_id,
            content="PRIVATE QUESTION", type="short_answer", answer={"correct_answer": "42"}, source={"source_name": "PRIVATE_FILENAME", "exam_id": 99})
        db.add(row); db.commit(); question_id = row.id
    request = TopicFromBank(title="Bài toán", question_id=question_id)
    assert forum.service.list_topics(actor=forum.users["other"])["total"] == 0
    assert forum.bank.get_question(question_id, actor=forum.users["owner"]).can_publish
    assert not forum.bank.get_question(question_id, actor=forum.users["admin"]).can_publish
    for role in ("other", "admin"): denied(404, lambda: forum.service.publish_bank_question(request, actor=forum.users[role]))
    denied(403, lambda: forum.service.publish_bank_question(request, actor=forum.users["viewer"]))
    public = forum.service.publish_bank_question(request, actor=forum.users["owner"])
    assert public["question"]["answer"]["correct_answer"] == "42"
    assert "PRIVATE_FILENAME" not in str(public) and "source" not in public["question"]
    denied(404, lambda: forum.bank.get_question(question_id, actor=forum.users["other"]))
    forum.bank.delete_question(question_id, actor=forum.users["owner"])
    assert forum.service.get_topic(public["id"], actor=forum.users["other"])["question"]["content"] == "PRIVATE QUESTION"

def test_replies_cross_topic_guard_and_tombstones(forum):
    first = topic(forum); second = topic(forum)
    parent = forum.service.add_comment(first["id"], CommentCreate(body="  Cách giải?  "), actor=forum.users["viewer"])
    child = forum.service.add_comment(first["id"], CommentCreate(body="Dùng công thức này", parent_id=parent["id"]), actor=forum.users["other"])
    denied(404, lambda: forum.service.add_comment(second["id"], CommentCreate(body="Sai chủ đề", parent_id=parent["id"]), actor=forum.users["owner"]))
    for role in ("owner", "admin"): denied(403, lambda: forum.service.delete_comment(first["id"], parent["id"], actor=forum.users[role]))
    forum.service.delete_comment(first["id"], parent["id"], actor=forum.users["viewer"])
    comments = forum.service.list_comments(first["id"], actor=forum.users["owner"])
    assert comments["items"][0]["body"] is None and comments["items"][0]["deleted"] and not comments["items"][0]["can_manage"]
    assert comments["items"][1]["id"] == child["id"] and comments["items"][1]["parent_id"] == parent["id"]
    assert forum.service.get_topic(first["id"], actor=forum.users["owner"])["comment_count"] == 1
    denied(404, lambda: forum.service.add_comment(first["id"], CommentCreate(body="Reply", parent_id=parent["id"]), actor=forum.users["owner"]))
    denied(404, lambda: forum.service.delete_comment(second["id"], child["id"], actor=forum.users["super"]))
    forum.service.delete_comment(first["id"], child["id"], actor=forum.users["super"])

def test_withdrawal_blocks_interactions_and_retains_private_copy(forum):
    created = topic(forum, answer={"correct_answer": "Tế bào"})
    saved = forum.service.save_to_bank(created["id"], actor=forum.users["other"])
    denied(403, lambda: forum.service.save_to_bank(created["id"], actor=forum.users["viewer"]))
    for role in ("other", "admin"): denied(403, lambda: forum.service.delete_topic(created["id"], actor=forum.users[role]))
    forum.service.delete_topic(created["id"], actor=forum.users["owner"])
    for role in ("owner", "other", "super"):
        assert forum.service.list_topics(actor=forum.users[role])["total"] == 0
        for call in (
            lambda: forum.service.get_topic(created["id"], actor=forum.users[role]),
            lambda: forum.service.list_comments(created["id"], actor=forum.users[role]),
            lambda: forum.service.add_comment(created["id"], CommentCreate(body="Reply"), actor=forum.users[role]),
            lambda: forum.service.save_to_bank(created["id"], actor=forum.users[role]),
        ): denied(404, call)
    assert forum.bank.get_question(saved["id"], actor=forum.users["other"]).answer["correct_answer"] == "Tế bào"
    denied(404, lambda: forum.bank.get_question(saved["id"], actor=forum.users["owner"]))
    another = topic(forum); forum.service.delete_topic(another["id"], actor=forum.users["super"])
    with forum.sessions() as db:
        actions = [a.action for a in db.query(AuditLog).all()]
        assert actions.count("community.topic_removed") == 2 and "community.question_saved" in actions
        assert all("Tế bào" not in str(a.details) for a in db.query(AuditLog).all())

def test_filters_pagination_and_literal_search(forum):
    for i in range(3): topic(forum, title=f"Bài {i}")
    matching = topic(forum, title="Tỉ lệ 100%", grade=8, type="essay", difficulty="van_dung")
    first = forum.service.list_topics(actor=forum.users["other"], page_size=2)
    second = forum.service.list_topics(actor=forum.users["other"], page_size=2, page=2)
    assert first["total"] == second["total"] == 4
    assert not {r["id"] for r in first["items"]} & {r["id"] for r in second["items"]}
    assert forum.service.list_topics(actor=forum.users["other"], search="%", grade=8, type="essay", difficulty="van_dung")["total"] == 1
    for i in range(3): forum.service.add_comment(matching["id"], CommentCreate(body=str(i)), actor=forum.users["other"])
    comments = forum.service.list_comments(matching["id"], actor=forum.users["owner"], page=2, page_size=2)
    assert comments["total"] == 3 and comments["items"][0]["body"] == "2"

def test_http_auth_validation_and_rate_limit(forum):
    with TestClient(forum.app) as client:
        assert client.get("/api/community/topics").status_code in (401, 403)
        forum.app.dependency_overrides[get_current_user] = lambda: forum.users["viewer"]
        payload = {"title": "Câu hỏi", "question": {"content": "Nội dung", "type": "essay"}}
        response = client.post("/api/community/topics", json=payload)
        assert response.status_code == 201; topic_id = response.json()["id"]
        for bad in (
            {**payload, "author_id": forum.users["owner"].id}, {**payload, "title": "  "},
            {**payload, "question": {"content": "   ", "type": "essay"}},
            {**payload, "question": {"content": "Nội dung", "type": "essay", "source": {"exam_id": 99}}},
            {**payload, "question": {"content": "Nội dung", "type": "essay", "answer": {"model_answer": "a" * 41000}}},
        ): assert client.post("/api/community/topics", json=bad).status_code == 422
        for query in ("page=0", "page_size=51", "grade=20", "type=unknown"):
            assert client.get("/api/community/topics?"+query).status_code == 422
        for body in ({"body": "  "}, {"body": "x" * 5001}, {"body": "test", "author_id": 1}):
            assert client.post(f"/api/community/topics/{topic_id}/comments", json=body).status_code == 422
        assert client.post(f"/api/community/topics/{topic_id}/save").status_code == 403
        routes.community_limiter.clear()
        for _ in range(30): assert client.post(f"/api/community/topics/{topic_id}/comments", json={"body": "Question?"}).status_code == 201
        limited = client.post(f"/api/community/topics/{topic_id}/comments", json={"body": "Question?"})
        assert limited.status_code == 429 and "retry-after" in limited.headers

def test_additive_tables_preserve_bank(forum):
    with forum.sessions() as db:
        row = BankQuestion(owner_user_id=forum.users["owner"].id, content="Keep private", type="essay")
        db.add(row); db.commit(); row_id = row.id
    Base.metadata.create_all(forum.engine); Base.metadata.create_all(forum.engine)
    assert {"community_topics", "community_comments"} <= set(inspect(forum.engine).get_table_names())
    assert forum.bank.get_question(row_id, actor=forum.users["owner"]).content == "Keep private"
    assert forum.service.list_topics(actor=forum.users["other"])["total"] == 0

def test_audit_failure_rolls_back_publication(forum, monkeypatch):
    import app.services.community_service as module
    def fail(*args, **kwargs): raise RuntimeError("Audit unavailable")
    monkeypatch.setattr(module, "record_audit", fail)
    with pytest.raises(RuntimeError): topic(forum)
    with forum.sessions() as db: assert db.query(CommunityTopic).count() == 0


@pytest.mark.parametrize("legacy_envelope", [False, True])
def test_bank_publication_projects_nested_answer_content(forum, legacy_envelope):
    private = {"source_name": "PRIVATE_FILENAME", "excerpt": "PRIVATE_EXCERPT", "document_id": 991}
    answer = {"question_id": "PRIVATE_QUESTION_ID", "model_answer": "Lời giải công khai",
              "explanation": "Giải thích công khai", "citations": [private],
              "answers": [{"statement_id": "s1", "is_true": True, "explanation": "Đúng vì...", "citations": [private]}]}
    rubric = {"question_id": "PRIVATE_QUESTION_ID", "total_score": 1,
              "criteria": [{"id": "c1", "name": "Lập luận", "max_score": 1,
                            "levels": [{"score": 1, "description": "Đầy đủ", "criteria": "Nêu đúng", "source": private}]}],
              "grading_guide": ["Chấp nhận cách giải tương đương"], "metadata": private}
    payload = {"answer": answer, "rubric": rubric} if legacy_envelope else {**answer, "rubric": rubric}
    with forum.sessions() as db:
        row = BankQuestion(owner_user_id=forum.users["owner"].id, content="Giải thích hiện tượng", type="essay",
                           answer=payload, source=private,
                           sub_questions=[{"id": "a", "content": "Nêu nguyên nhân", "score": 1, "metadata": private}])
        db.add(row); db.commit(); question_id = row.id
    published = forum.service.publish_bank_question(TopicFromBank(title="Thảo luận", question_id=question_id), actor=forum.users["owner"])
    assert "PRIVATE_" not in str(published)
    public_answer = published["question"]["answer"]
    assert public_answer["model_answer"] == "Lời giải công khai"
    assert public_answer["rubric"]["criteria"][0]["levels"][0]["criteria"] == "Nêu đúng"
    assert public_answer["rubric"]["grading_guide"] == rubric["grading_guide"]
    assert public_answer["answers"][0]["explanation"] == "Đúng vì..."
    assert "PRIVATE_FILENAME" in str(forum.bank.get_question(question_id, actor=forum.users["owner"]).answer)


def test_legacy_topic_reads_and_copies_exclude_private_nested_fields(forum):
    created = topic(forum, answer={"correct_answer": "42"})
    with forum.sessions() as db:
        row = db.get(CommunityTopic, created["id"])
        row.question = {**row.question, "answer": {"correct_answer": "42", "citations": [{"source_name": "PRIVATE_FILENAME"}]},
                        "source": {"exam_id": 123, "source_name": "PRIVATE_FILENAME"}}
        db.commit()
    public = forum.service.get_topic(created["id"], actor=forum.users["other"])
    assert "PRIVATE_FILENAME" not in str(public)
    saved = forum.service.save_to_bank(created["id"], actor=forum.users["other"])
    copy = forum.bank.get_question(saved["id"], actor=forum.users["other"])
    assert copy.answer["correct_answer"] == "42"
    assert "PRIVATE_FILENAME" not in str(copy)
