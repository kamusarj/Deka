"""Ngân hàng câu hỏi (Phase 2). CRUD + lưu câu đã duyệt từ đề. Không gọi AI."""

from fastapi import HTTPException

from app.core.database import get_session_factory, init_db
from app.models.bank_question import BankQuestion
from app.models.exam import Exam
from app.schemas.bank_question import (
    BankQuestionCreate,
    BankQuestionDeleteResponse,
    BankQuestionResponse,
    SaveFromExamRequest,
    SaveFromExamResponse,
)
from app.services.authorization import (
    ownership_values,
    require_resource_access,
    require_resource_mutation,
    scope_query,
)
from app.core.config import settings
from app.services.question_duplicates import DuplicateDetector, bank_candidates, task_text
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.rich_content import normalize_blocks


class QuestionBankService:
    def __init__(self):
        init_db()
        self.SessionLocal = get_session_factory()

    def add_question(self, payload: BankQuestionCreate, actor=None) -> BankQuestionResponse:
        with self.SessionLocal() as db:
            findings = self._check_duplicates(db, payload.model_dump(), actor, grade=payload.grade)
            question = BankQuestion(
                content=payload.content,
                type=payload.type,
                difficulty=payload.difficulty,
                topic=payload.topic,
                grade=payload.grade,
                subject=payload.subject,
                tags=payload.tags,
                options=payload.options,
                statements=payload.statements,
                sub_questions=payload.sub_questions,
                answer=payload.answer,
                source=payload.source or self._bank_source("manual_input"),
                rich_content=self._rich_blocks([item.model_dump() for item in payload.rich_content or []]),
                **ownership_values(actor),
            )
            db.add(question)
            db.commit()
            db.refresh(question)
            response = self._to_response(question, actor)
            response.duplicate_findings = findings
            return response

    def save_from_exam(self, request: SaveFromExamRequest, actor=None) -> SaveFromExamResponse:
        with self.SessionLocal() as db:
            exam = db.get(Exam, request.exam_id)
            if not exam:
                raise HTTPException(status_code=404, detail="Không tìm thấy đề kiểm tra")
            require_resource_access(exam, actor)
            if (exam.publication_status or "verified") != "verified":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Bản nháp chưa qua kiểm định bắt buộc nên chưa thể lưu "
                        "câu hỏi vào ngân hàng."
                    ),
                )

            selected_ids = self._selected_question_ids(exam, request.question_ids)
            if not selected_ids:
                raise HTTPException(
                    status_code=400,
                    detail="Không có câu hỏi nào để lưu (chưa duyệt 'accepted' hoặc id không hợp lệ).",
                )

            answer_by_id = {
                answer.get("question_id"): answer
                for answer in (exam.answer_key or [])
            }
            rubric_by_id = {
                item.get("question_id"): item
                for item in (exam.rubric or [])
            }

            saved_models = []
            duplicate_findings = []
            detector = DuplicateDetector(bank_candidates(db, actor)) if settings.DUPLICATE_DETECTION_ENABLED else None
            pending_candidates = []
            for question in exam.questions or []:
                if question.get("id") not in selected_ids:
                    continue
                answer = answer_by_id.get(question["id"])
                rubric = rubric_by_id.get(question["id"])
                duplicate_findings.extend(self._check_duplicates(db, {**question, "answer": answer}, actor, grade=exam.grade, detector=detector))
                if pending_candidates:
                    duplicate_findings.extend(self._check_duplicates(db, {**question, "answer": answer}, actor, grade=exam.grade, detector=DuplicateDetector(pending_candidates)))
                pending_candidates.append({**question, "answer": answer})
                metadata = question.get("metadata") or {}
                bank_question = BankQuestion(
                    content=question.get("content", ""),
                    type=question.get("type", "multiple_choice"),
                    difficulty=question.get("difficulty", "thong_hieu"),
                    topic=metadata.get("topic"),
                    grade=exam.grade,
                    subject=exam.subject,
                    tags=request.tags,
                    options=question.get("options"),
                    statements=question.get("statements"),
                    sub_questions=question.get("sub_questions"),
                    answer=self._saved_answer_payload(answer, rubric),
                    rich_content=self._rich_blocks(question.get("rich_content")),
                    content_metadata=metadata,
                    source=self._bank_source(
                        "question_bank",
                        origin=question.get("source"),
                        exam_id=exam.id,
                    ),
                    **ownership_values(actor),
                )
                db.add(bank_question)
                saved_models.append(bank_question)

            db.commit()
            for model in saved_models:
                db.refresh(model)
            saved = [self._to_response(model, actor) for model in saved_models]
            return SaveFromExamResponse(saved=saved, count=len(saved), duplicate_findings=duplicate_findings)

    @staticmethod
    def _rich_blocks(value):
        try:
            return normalize_blocks(value)
        except (ValueError, OSError) as error:
            raise HTTPException(422, "Nội dung công thức/ảnh/bảng chưa hợp lệ.") from error

    @staticmethod
    def _check_duplicates(db, question, actor, *, grade=None, detector=None):
        if not settings.DUPLICATE_DETECTION_ENABLED:
            return []
        detector = detector or DuplicateDetector(bank_candidates(db, actor))
        findings = detector.check(question)
        if any(item["decision"] == "reject" for item in findings):
            raise HTTPException(status_code=409, detail={"message": "Câu hỏi này đã có trong ngân hàng. Hãy sử dụng câu đã lưu.", "duplicate_findings": findings})
        return findings

    def semantic_search(self, query: str, *, grade=None, limit=20, actor=None, type=None, difficulty=None):
        with self.SessionLocal() as db:
            records = [q for q in bank_candidates(db, actor, grade=grade) if (not type or q["type"] == type) and (not difficulty or q.get("difficulty") == difficulty)]
            chunks = [{"id": f"bank_{q['id']}", "text": task_text(q), "metadata": {"question_id": q["id"]}} for q in records]
            hits = KnowledgeBaseService._retriever_for(chunks).retrieve(query, k=limit)
            result = []
            for hit in hits:
                row = db.get(BankQuestion, int(hit["chunk"]["metadata"]["question_id"]))
                # Candidates have already been authorized; keep the boundary
                # explicit when resolving records from retrieved IDs.
                require_resource_access(row, actor)
                result.append({"question": self._to_response(row, actor).model_dump(), "score": hit["score"]})
            return result

    def list_questions(
        self,
        *,
        grade: int | None = None,
        subject: str | None = None,
        topic: str | None = None,
        type: str | None = None,
        difficulty: str | None = None,
        search: str | None = None,
        actor=None,
    ) -> list[BankQuestionResponse]:
        with self.SessionLocal() as db:
            query = scope_query(db.query(BankQuestion), BankQuestion, actor)
            if grade is not None:
                query = query.filter(BankQuestion.grade == grade)
            if subject:
                query = query.filter(BankQuestion.subject == subject)
            if topic:
                query = query.filter(BankQuestion.topic == topic)
            if type:
                query = query.filter(BankQuestion.type == type)
            if difficulty:
                query = query.filter(BankQuestion.difficulty == difficulty)
            if search:
                query = query.filter(BankQuestion.content.ilike(f"%{search}%"))
            questions = query.order_by(
                BankQuestion.created_at.desc(), BankQuestion.id.desc()
            ).all()
            return [self._to_response(question, actor) for question in questions]

    def get_question(self, question_id: int, actor=None) -> BankQuestionResponse:
        with self.SessionLocal() as db:
            return self._to_response(self._get_model(db, question_id, actor), actor)

    def delete_question(self, question_id: int, actor=None) -> BankQuestionDeleteResponse:
        with self.SessionLocal() as db:
            question = self._get_model(db, question_id, actor)
            require_resource_mutation(question, actor)
            db.delete(question)
            db.commit()
            return BankQuestionDeleteResponse(id=question_id)

    def bump_usage(self, question_id: int, actor=None) -> BankQuestionResponse:
        with self.SessionLocal() as db:
            question = self._get_model(db, question_id, actor)
            require_resource_mutation(question, actor)
            question.usage_count = (question.usage_count or 0) + 1
            db.commit()
            db.refresh(question)
            return self._to_response(question, actor)

    def _selected_question_ids(self, exam: Exam, question_ids: list[str]) -> set[str]:
        valid_ids = {question.get("id") for question in (exam.questions or [])}
        if question_ids:
            return {qid for qid in question_ids if qid in valid_ids}
        review_status = exam.review_status or {}
        return {
            qid
            for qid, status in review_status.items()
            if status.get("status") == "accepted" and qid in valid_ids
        }

    def _bank_source(self, source_type: str, *, origin=None, exam_id=None) -> dict:
        source = {
            "source_type": source_type,
            "source_name": f"exam_{exam_id}" if exam_id else "Ngân hàng câu hỏi",
            "source_page": None,
            "confidence_score": 1.0,
        }
        if origin:
            source["origin"] = origin
        return source

    @staticmethod
    def _saved_answer_payload(answer: dict | None, rubric: dict | None) -> dict | None:
        """Keep saved answers directly consumable while retaining essay rubrics.

        Older rows used ``{"answer": ..., "rubric": ...}``, which made clients
        unwrap an internal persistence envelope before they could show an
        answer. New rows use the same answer shape as an exam answer-key item.
        """
        if not answer and not rubric:
            return None
        payload = dict(answer or {})
        if rubric:
            payload["rubric"] = rubric
        return payload

    def _get_model(self, db, question_id: int, actor=None) -> BankQuestion:
        question = db.get(BankQuestion, question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi trong ngân hàng")
        return require_resource_access(question, actor)

    def _to_response(self, question: BankQuestion, actor=None) -> BankQuestionResponse:
        return BankQuestionResponse(
            can_publish=actor is not None and actor.role in {"teacher", "school_admin", "super_admin"} and (actor.id == question.owner_user_id or actor.role == "super_admin"),
            id=question.id,
            content=question.content,
            type=question.type,
            difficulty=question.difficulty,
            topic=question.topic,
            grade=question.grade,
            subject=question.subject,
            tags=question.tags or [],
            options=question.options,
            statements=question.statements,
            sub_questions=question.sub_questions,
            answer=question.answer,
            source=question.source,
            rich_content=question.rich_content,
            content_metadata=question.content_metadata,
            usage_count=question.usage_count or 0,
            rating=question.rating,
            created_at=question.created_at,
        )
