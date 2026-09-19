from app.api.response_privacy import ContentPrivacyRoute
import asyncio
from app.services.ai.operations import run_billable
from fastapi import APIRouter, Depends, Query

from app.models.user import User
from app.schemas.bank_question import (
    BankQuestionCreate,
    BankQuestionDeleteResponse,
    BankQuestionResponse,
    SaveFromExamRequest,
    SaveFromExamResponse,
)
from app.services.auth_service import get_current_user, require_content_writer
from app.services.question_bank_service import QuestionBankService

router = APIRouter(route_class=ContentPrivacyRoute, prefix="/question-bank", tags=["question-bank"])
bank_service = QuestionBankService()


@router.post("", response_model=BankQuestionResponse)
def add_question(payload: BankQuestionCreate, user: User = Depends(require_content_writer)):
    """Thêm thủ công một câu hỏi vào ngân hàng."""
    return bank_service.add_question(payload, actor=user)


@router.post("/save-from-exam", response_model=SaveFromExamResponse)
def save_from_exam(request: SaveFromExamRequest, user: User = Depends(require_content_writer)):
    """Lưu các câu đã duyệt 'accepted' (hoặc theo danh sách id) từ một đề vào ngân hàng."""
    return bank_service.save_from_exam(request, actor=user)


@router.get("", response_model=list[BankQuestionResponse])
async def list_questions(
    grade: int | None = None,
    subject: str | None = None,
    topic: str | None = None,
    type: str | None = None,
    difficulty: str | None = None,
    search: str | None = None,
    user: User = Depends(get_current_user),
):
    """Liệt kê + lọc câu hỏi ngân hàng."""
    return bank_service.list_questions(
        grade=grade,
        subject=subject,
        topic=topic,
        type=type,
        difficulty=difficulty,
        search=search, actor=user,
    )


@router.get("/search/semantic")
async def semantic_search(
    query: str = Query(min_length=1, max_length=2000),
    grade: int | None = Query(default=None, ge=6, le=9),
    limit: int = Query(default=20, ge=1, le=100),
    type: str | None = None,
    difficulty: str | None = None,
    user: User = Depends(get_current_user),
):
    return await run_billable(user, lambda: asyncio.to_thread(bank_service.semantic_search, query, grade=grade, limit=limit, actor=user, type=type, difficulty=difficulty), "bank_search")


@router.get("/{question_id}", response_model=BankQuestionResponse)
async def get_question(question_id: int, user: User = Depends(get_current_user)):
    """Chi tiết một câu hỏi ngân hàng."""
    return bank_service.get_question(question_id, actor=user)


@router.post("/{question_id}/use", response_model=BankQuestionResponse)
async def use_question(question_id: int, user: User = Depends(require_content_writer)):
    """Tăng usage_count khi câu hỏi được dùng lại."""
    return bank_service.bump_usage(question_id, actor=user)


@router.delete("/{question_id}", response_model=BankQuestionDeleteResponse)
async def delete_question(question_id: int, user: User = Depends(require_content_writer)):
    """Xóa một câu hỏi khỏi ngân hàng."""
    return bank_service.delete_question(question_id, actor=user)
