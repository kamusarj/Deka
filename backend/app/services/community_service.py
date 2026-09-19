from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, or_

from app.core.database import get_session_factory, init_db
from app.models.bank_question import BankQuestion
from app.models.community import CommunityComment, CommunityTopic
from app.models.user import User
from app.schemas.community import CommunityQuestion
from app.services.audit_service import record_audit
from app.services.authorization import ownership_values
from app.services.community_snapshot import public_question_snapshot
from app.services.role_policy import KNOWN_ROLES, can_write_content


class CommunityService:
    def __init__(self):
        init_db()
        self.SessionLocal = get_session_factory()

    @staticmethod
    def require_member(actor):
        if actor is None or not actor.is_active or actor.role not in KNOWN_ROLES:
            raise HTTPException(403, "Bạn không có quyền tham gia cộng đồng")

    @staticmethod
    def can_manage(row, actor):
        return actor.id == row.author_id or actor.role == "super_admin"

    @staticmethod
    def _author(user):
        return {"id": user.id, "name": user.name or "Thành viên"} if user and not user.deleted_at else {"id": None, "name": "Tài khoản đã xóa"}

    @staticmethod
    def _topic(db, topic_id, lock=False):
        query = db.query(CommunityTopic).filter(CommunityTopic.id == topic_id, CommunityTopic.deleted_at.is_(None))
        if lock:
            query = query.with_for_update()
        row = query.first()
        if row is None:
            raise HTTPException(404, "Chủ đề không tồn tại hoặc đã được gỡ")
        return row

    def _response(self, db, row, actor, *, detail=True, author=None, count=None):
        result = {
            "id": row.id, "title": row.title, "preview": row.content[:350],
            "grade": row.grade, "type": row.type, "difficulty": row.difficulty,
            "author": self._author(author or db.get(User, row.author_id)),
            "created_at": row.created_at, "can_manage": self.can_manage(row, actor),
            "comment_count": count if count is not None else db.query(func.count(CommunityComment.id)).filter(
                CommunityComment.topic_id == row.id, CommunityComment.deleted_at.is_(None)).scalar(),
        }
        if detail:
            result["question"] = public_question_snapshot(row.question)
        return result

    def list_topics(self, *, actor, page=1, page_size=20, search=None, grade=None, type=None, difficulty=None):
        self.require_member(actor)
        with self.SessionLocal() as db:
            query = db.query(CommunityTopic).filter(CommunityTopic.deleted_at.is_(None))
            if search and search.strip():
                term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                query = query.filter(or_(CommunityTopic.title.ilike(f"%{term}%", escape="\\"), CommunityTopic.content.ilike(f"%{term}%", escape="\\")))
            for name, value in (("grade", grade), ("type", type), ("difficulty", difficulty)):
                if value is not None:
                    query = query.filter(getattr(CommunityTopic, name) == value)
            total = query.count()
            rows = query.order_by(CommunityTopic.created_at.desc(), CommunityTopic.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
            authors = {u.id: u for u in db.query(User).filter(User.id.in_({r.author_id for r in rows})).all()}
            counts = dict(db.query(CommunityComment.topic_id, func.count(CommunityComment.id)).filter(
                CommunityComment.topic_id.in_([r.id for r in rows]), CommunityComment.deleted_at.is_(None)
            ).group_by(CommunityComment.topic_id).all())
            return {"items": [self._response(db, r, actor, detail=False, author=authors.get(r.author_id), count=counts.get(r.id, 0)) for r in rows], "total": total, "page": page, "page_size": page_size}

    def get_topic(self, topic_id, *, actor):
        self.require_member(actor)
        with self.SessionLocal() as db:
            return self._response(db, self._topic(db, topic_id), actor)

    def _create(self, db, title, question, actor):
        snapshot = public_question_snapshot(question.model_dump())
        row = CommunityTopic(author_id=actor.id, title=title, content=question.content,
                             grade=question.grade, type=question.type, difficulty=question.difficulty, question=snapshot)
        db.add(row)
        db.flush()
        record_audit(db, actor=actor, action="community.topic_published", target_type="community_topic", target_id=row.id)
        db.commit()
        db.refresh(row)
        return self._response(db, row, actor)

    def create_topic(self, request, *, actor):
        self.require_member(actor)
        with self.SessionLocal() as db:
            return self._create(db, request.title, request.question, actor)

    def publish_bank_question(self, request, *, actor):
        self.require_member(actor)
        if not can_write_content(actor.role):
            raise HTTPException(403, "Bạn không có quyền chia sẻ từ ngân hàng riêng")
        with self.SessionLocal() as db:
            row = db.get(BankQuestion, request.question_id)
            if row is None or (row.owner_user_id != actor.id and actor.role != "super_admin"):
                raise HTTPException(404, "Không tìm thấy câu hỏi thuộc quyền chia sẻ của bạn")
            fields = set(CommunityQuestion.model_fields) - {"source"}
            try:
                question = CommunityQuestion.model_validate({field: getattr(row, field) for field in fields})
            except ValidationError as error:
                raise HTTPException(422, "Câu hỏi chưa phù hợp để đăng; hãy tạo chủ đề mới với nội dung đã chỉnh sửa") from error
            return self._create(db, request.title, question, actor)

    def delete_topic(self, topic_id, *, actor):
        self.require_member(actor)
        with self.SessionLocal() as db:
            row = self._topic(db, topic_id, lock=True)
            if not self.can_manage(row, actor):
                raise HTTPException(403, "Chỉ người đăng hoặc Super Admin được gỡ chủ đề")
            row.deleted_at = datetime.now(timezone.utc)
            record_audit(db, actor=actor, action="community.topic_removed", target_type="community_topic", target_id=row.id)
            db.commit()
            return {"id": topic_id, "deleted": True}

    def list_comments(self, topic_id, *, actor, page=1, page_size=50):
        self.require_member(actor)
        with self.SessionLocal() as db:
            self._topic(db, topic_id)
            query = db.query(CommunityComment).filter(CommunityComment.topic_id == topic_id)
            total = query.count()
            rows = query.order_by(CommunityComment.id).offset((page - 1) * page_size).limit(page_size).all()
            authors = {u.id: u for u in db.query(User).filter(User.id.in_({r.author_id for r in rows})).all()}
            return {"items": [{"id": r.id, "parent_id": r.parent_id,
                              "body": None if r.deleted_at else r.body,
                              "deleted": bool(r.deleted_at), "author": self._author(authors.get(r.author_id)),
                              "created_at": r.created_at, "can_manage": not r.deleted_at and self.can_manage(r, actor)} for r in rows],
                    "total": total, "page": page, "page_size": page_size}

    def add_comment(self, topic_id, request, *, actor):
        self.require_member(actor)
        with self.SessionLocal() as db:
            self._topic(db, topic_id, lock=True)
            if request.parent_id:
                parent = db.get(CommunityComment, request.parent_id)
                if parent is None or parent.topic_id != topic_id or parent.deleted_at:
                    raise HTTPException(404, "Bình luận được trả lời không tồn tại hoặc đã được gỡ")
            row = CommunityComment(topic_id=topic_id, author_id=actor.id, body=request.body, parent_id=request.parent_id)
            db.add(row)
            db.flush()
            record_audit(db, actor=actor, action="community.comment_created", target_type="community_comment", target_id=row.id, details={"topic_id": topic_id})
            db.commit()
            return {"id": row.id}

    def delete_comment(self, topic_id, comment_id, *, actor):
        self.require_member(actor)
        with self.SessionLocal() as db:
            self._topic(db, topic_id, lock=True)
            row = db.get(CommunityComment, comment_id)
            if row is None or row.topic_id != topic_id or row.deleted_at:
                raise HTTPException(404, "Không tìm thấy bình luận")
            if not self.can_manage(row, actor):
                raise HTTPException(403, "Chỉ người viết hoặc Super Admin được gỡ bình luận")
            row.deleted_at = datetime.now(timezone.utc)
            record_audit(db, actor=actor, action="community.comment_removed", target_type="community_comment", target_id=row.id, details={"topic_id": topic_id})
            db.commit()
            return {"id": comment_id, "deleted": True}

    def save_to_bank(self, topic_id, *, actor):
        self.require_member(actor)
        if not can_write_content(actor.role):
            raise HTTPException(403, "Bạn không có quyền ghi vào ngân hàng câu hỏi")
        with self.SessionLocal() as db:
            topic = self._topic(db, topic_id, lock=True)
            row = BankQuestion(**public_question_snapshot(topic.question), **ownership_values(actor),
                               source={"source_type": "community", "source_name": "Cộng đồng", "community_topic_id": topic.id})
            db.add(row)
            db.flush()
            record_audit(db, actor=actor, action="community.question_saved", target_type="bank_question", target_id=row.id, details={"topic_id": topic_id})
            db.commit()
            return {"id": row.id}
