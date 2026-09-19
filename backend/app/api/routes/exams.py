from app.api.response_privacy import ContentPrivacyRoute
from typing import Literal
from contextlib import aclosing

from fastapi import Header, APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.models.user import User
from app.schemas.exam import (
    ExamDeleteResponse,
    ExamResponse,
    ExamSearchResponse,
    FullExamRequest,
    FullExamResponse,
    MatrixRequest,
    MatrixResponse,
    RegenerateQuestionsRequest,
    RegenerateQuestionsResponse,
    ReviewQuestionsRequest,
    SpecificationRequest,
    SpecificationResponse,
)
from app.services.ai_provider_chain import (
    reset_provider_fallback_allowed,
    set_provider_fallback_allowed,
)
from app.services.auth_service import (
    get_current_user,
    require_ai_request,
    require_content_writer,
)
from app.services.exam_service import ExamService
from app.services.exam.export_document import ExportDocument
from app.schemas.question_edit import QuestionEditRequest
from app.services.ai.operations import run_billable, billable_stream

router = APIRouter(route_class=ContentPrivacyRoute)
exam_service = ExamService()


@router.post("/generate-matrix", response_model=MatrixResponse)
async def generate_matrix(request: MatrixRequest, _user: User = Depends(require_ai_request)):
    """Tạo ma trận đề kiểm tra."""
    return await run_billable(_user, lambda: exam_service.generate_matrix(request), "matrix_generation")


@router.post("/generate-specification", response_model=SpecificationResponse)
async def generate_specification(request: SpecificationRequest, _user: User = Depends(require_ai_request)):
    """Tạo bản đặc tả đề kiểm tra."""
    return await run_billable(_user, lambda: exam_service.generate_specification(request), "specification_generation")


@router.post("/generate-full-exam", response_model=FullExamResponse)
async def generate_full_exam(request: FullExamRequest, user: User = Depends(require_ai_request), idempotency_key: str | None = Header(None, min_length=1, max_length=128)):
    """Tạo đề kiểm tra hoàn chỉnh (ma trận + đặc tả + đề + đáp án)."""
    token = set_provider_fallback_allowed(request.allow_provider_fallback)
    try:
        return await run_billable(user, lambda: exam_service.generate_full_exam(request, actor=user), idempotency_key=idempotency_key, payload=request)
    finally:
        reset_provider_fallback_allowed(token)


@router.post("/generate-full-exam/stream")
async def generate_full_exam_stream(request: FullExamRequest, user: User = Depends(require_ai_request), idempotency_key: str | None = Header(None, min_length=1, max_length=128)):
    """Tạo đề kiểm tra với SSE streaming — hiển thị pipeline progress real-time."""
    async def policy_stream():
        token = set_provider_fallback_allowed(request.allow_provider_fallback)
        try:
            async with aclosing(billable_stream(user, lambda: exam_service.generate_full_exam_stream(request, actor=user), idempotency_key=idempotency_key, payload=request)) as source:
                async for event in source:
                    yield event
        finally:
            reset_provider_fallback_allowed(token)

    return StreamingResponse(
        policy_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{exam_id}/review", response_model=FullExamResponse)
async def review_questions(exam_id: int, request: ReviewQuestionsRequest, user: User = Depends(require_content_writer)):
    """Lưu trạng thái duyệt từng câu hỏi."""
    return await exam_service.review_questions(exam_id, request, actor=user)


@router.get("/{exam_id}/questions/{question_id}/bank-template/{bank_id}", response_model=QuestionEditRequest, response_model_exclude_none=True)
def bank_edit_template(exam_id: int, question_id: str, bank_id: int, version_id: int = Query(ge=1), user: User = Depends(require_content_writer)):
    return exam_service.bank_edit_template(exam_id, question_id, bank_id, version_id=version_id, actor=user)


@router.patch("/{exam_id}/questions/{question_id}", response_model=FullExamResponse)
async def edit_question(exam_id: int, question_id: str, request: QuestionEditRequest,
                        user: User = Depends(require_ai_request)):
    """Save a teacher revision and independently verify only that revision."""
    token = set_provider_fallback_allowed(False)
    try:
        return await run_billable(user, lambda: exam_service.edit_question(exam_id, question_id, request, actor=user), "question_edit")
    finally:
        reset_provider_fallback_allowed(token)


@router.post("/regenerate-questions", response_model=RegenerateQuestionsResponse)
async def regenerate_questions(request: RegenerateQuestionsRequest, user: User = Depends(require_ai_request)):
    """Tạo lại có chọn lọc các câu hỏi trong một đề đã lưu."""
    token = set_provider_fallback_allowed(request.allow_provider_fallback)
    try:
        return await run_billable(user, lambda: exam_service.regenerate_questions(request, actor=user), "question_regeneration")
    finally:
        reset_provider_fallback_allowed(token)


@router.get("", response_model=list[ExamResponse])
async def list_exams(
    grade: int | None = None,
    exam_type: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    user: User = Depends(get_current_user),
):
    """Danh sách đề đã tạo (lọc theo khối/loại kiểm tra, phân trang tùy chọn)."""
    return await exam_service.list_exams(
        grade=grade, exam_type=exam_type, limit=limit, offset=offset, actor=user
    )


@router.get("/search", response_model=ExamSearchResponse)
async def search_exams(
    subject: str | None = None,
    grade: int | None = None,
    exam_type: str | None = None,
    owner_user_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
):
    return await exam_service.search_exams(
        subject=subject,
        grade=grade,
        exam_type=exam_type,
        owner_user_id=owner_user_id,
        page=page,
        page_size=page_size,
        actor=user,
    )


@router.get("/{exam_id}", response_model=FullExamResponse)
async def get_exam(exam_id: int, user: User = Depends(get_current_user)):
    """Chi tiết đề kiểm tra."""
    return await exam_service.get_exam(exam_id, actor=user)


@router.delete("/{exam_id}", response_model=ExamDeleteResponse)
async def delete_exam(exam_id: int, user: User = Depends(require_content_writer)):
    """Xóa một đề kiểm tra khỏi lịch sử."""
    return await exam_service.delete_exam(exam_id, actor=user)


@router.post("/{exam_id}/duplicate", response_model=FullExamResponse)
async def duplicate_exam(exam_id: int, user: User = Depends(require_content_writer)):
    """Nhân bản một đề (id mới, nội dung giống, trạng thái duyệt reset)."""
    return await exam_service.duplicate_exam(exam_id, actor=user)


@router.post("/{exam_id}/export-docx")
async def export_docx(
    exam_id: int,
    audience: Literal["student", "teacher"] = "teacher",
    document: ExportDocument = "exam",
    variant_code: str | None = Query(default=None, pattern=r"^\d{3}$"),
    user: User = Depends(get_current_user),
):
    """Export đề kiểm tra ra file Word."""
    return await exam_service.export_docx(exam_id, actor=user, audience=audience, document=document, variant_code=variant_code)


@router.post("/{exam_id}/export-pdf")
async def export_pdf(
    exam_id: int,
    audience: Literal["student", "teacher"] = "teacher",
    document: ExportDocument = "exam",
    variant_code: str | None = Query(default=None, pattern=r"^\d{3}$"),
    user: User = Depends(get_current_user),
):
    """Export đề kiểm tra ra file PDF (font Unicode tiếng Việt)."""
    return await exam_service.export_pdf(exam_id, actor=user, audience=audience, document=document, variant_code=variant_code)
