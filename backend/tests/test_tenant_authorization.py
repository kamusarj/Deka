"""Authorization regression tests for tenant-owned persisted resources."""

from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.database import get_session_factory
from app.models.user import User
from app.schemas.bank_question import BankQuestionCreate
from app.schemas.exam import FullExamRequest
from app.services.auth_service import hash_password
from app.services.document_service import DocumentService
from app.services.exam_service import ExamService
from app.services.question_bank_service import QuestionBankService


def _second_teacher() -> User:
    with get_session_factory()() as db:
        user = User(
            email=f"tenant-{uuid4().hex}@example.test",
            password_hash=hash_password("not-used-in-test"),
            name="Other Teacher",
            role="teacher",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        # The services need only scalar identity fields after the session closes.
        return SimpleNamespace(id=user.id, school_id=user.school_id, role=user.role)


def _clean_user(user_id: int) -> None:
    with get_session_factory()() as db:
        user = db.get(User, user_id)
        if user:
            db.delete(user)
            db.commit()


def _exam_payload() -> FullExamRequest:
    return FullExamRequest(
        school="THCS Test", grade=8, subject="Khoa học tự nhiên",
        exam_type="Giữa học kì I", duration_minutes=45, school_year="2025-2026",
        total_score=10,
        curriculum=[{
            "topic": "Phản ứng hóa học", "periods": 10,
            "achievements": ["Trình bày được khái niệm phản ứng hóa học."],
        }],
        difficulty_ratio={"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30},
    )


def _docx_bytes() -> bytes:
    from docx import Document

    document = Document()
    document.add_paragraph("Tài liệu riêng tư")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_teacher_cannot_read_other_teacher_persisted_resources(auth_context):
    owner = auth_context["user"]
    other = _second_teacher()
    documents = DocumentService()
    bank = QuestionBankService()
    exams = ExamService()
    for name in (
        "resource_agent", "matrix_agent", "spec_agent", "question_agent",
        "answer_agent", "validator_agent", "verification_agent",
    ):
        getattr(exams, name).has_ai = False

    document = documents.save_document(
        filename="private.docx", data=_docx_bytes(), actor=owner,
    )
    question = bank.add_question(BankQuestionCreate(
        content="Câu hỏi riêng tư", type="multiple_choice", difficulty="nhan_biet",
        options=[{"key": "A", "text": "Đúng"}],
    ), actor=owner)
    exam = await exams.generate_full_exam(_exam_payload(), actor=owner)
    try:
        assert all(item.id != question.id for item in bank.list_questions(actor=other))
        assert all(item.id != exam.id for item in await exams.list_exams(actor=other))
        assert all(item.id != document.id for item in documents.list_documents(actor=other))
        with pytest.raises(HTTPException) as question_error:
            bank.get_question(question.id, actor=other)
        with pytest.raises(HTTPException) as exam_error:
            await exams.get_exam(exam.id, actor=other)
        with pytest.raises(HTTPException) as document_error:
            documents.get_document(document.id, actor=other)
        assert question_error.value.status_code == exam_error.value.status_code == document_error.value.status_code == 404
    finally:
        bank.delete_question(question.id, actor=owner)
        await exams.delete_exam(exam.id, actor=owner)
        documents.delete_document(document.id, actor=owner)
        _clean_user(other.id)
