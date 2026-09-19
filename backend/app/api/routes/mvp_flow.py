from app.api.response_privacy import ContentPrivacyRoute
from fastapi import APIRouter, Depends

from app.models.user import User
from app.schemas.exam import (
    AnswerGenerateRequest,
    AnswerGenerateResponse,
    ConfirmCurriculumRequest,
    ConfirmCurriculumResponse,
    CurriculumAnalyzeRequest,
    CurriculumAnalyzeResponse,
    DataIngestRequest,
    DataIngestResponse,
    DataNormalizeRequest,
    DataNormalizeResponse,
    ExportRequest,
    FullExamResponse,
    MatrixRequest,
    MatrixResponse,
    QuestionsGenerateRequest,
    QuestionsGenerateResponse,
    RegenerateQuestionsRequest,
    RegenerateQuestionsResponse,
    ResourceCollectRequest,
    ResourceCollectResponse,
    ReviewQuestionsRequest,
    SpecificationRequest,
    SpecificationResponse,
    ValidationRequest,
    ValidationResponse,
)
from app.services.ai_provider_chain import (
    reset_provider_fallback_allowed,
    set_provider_fallback_allowed,
)
from app.services.auth_service import get_current_user, require_ai_request
from app.services.exam_service import ExamService
from app.services.ai.operations import run_billable

router = APIRouter(route_class=ContentPrivacyRoute, dependencies=[Depends(require_ai_request)])
exam_service = ExamService()


@router.post("/resources/collect", response_model=ResourceCollectResponse, tags=["resources"])
async def collect_resources(request: ResourceCollectRequest):
    return await exam_service.collect_resources(request)


@router.post("/data/ingest", response_model=DataIngestResponse, tags=["data"])
async def ingest_data(request: DataIngestRequest):
    """Step 0: Nạp nguồn dữ liệu đã kiểm soát từ local JSON Phase 1."""
    return await exam_service.ingest_data(request)


@router.post("/curriculum/analyze", response_model=CurriculumAnalyzeResponse, tags=["curriculum"])
async def analyze_curriculum(request: CurriculumAnalyzeRequest):
    return await exam_service.analyze_curriculum(request)


@router.post("/data/normalize", response_model=DataNormalizeResponse, tags=["data"])
async def normalize_data(request: DataNormalizeRequest):
    """Step 1: Chuẩn hóa dữ liệu về schema chung."""
    return await exam_service.normalize_data(request)


@router.post("/curriculum/confirm", response_model=ConfirmCurriculumResponse, tags=["curriculum"])
async def confirm_curriculum(request: ConfirmCurriculumRequest):
    """Giáo viên xác nhận phạm vi kiểm tra trước khi tạo ma trận."""
    return await exam_service.confirm_curriculum(request)


@router.post("/matrix/generate", response_model=MatrixResponse, tags=["matrix"])
async def generate_matrix(request: MatrixRequest, user: User = Depends(get_current_user)):
    return await run_billable(user, lambda: exam_service.generate_matrix(request), "matrix_generation")


@router.post("/specification/generate", response_model=SpecificationResponse, tags=["specification"])
async def generate_specification(request: SpecificationRequest, user: User = Depends(get_current_user)):
    return await run_billable(user, lambda: exam_service.generate_specification(request), "specification_generation")


@router.post("/questions/generate", response_model=QuestionsGenerateResponse, tags=["questions"])
async def generate_questions(request: QuestionsGenerateRequest, user: User = Depends(get_current_user)):
    return await run_billable(user, lambda: exam_service.generate_questions(request), "question_generation")


@router.post("/questions/regenerate", response_model=RegenerateQuestionsResponse, tags=["questions"])
async def regenerate_questions(request: RegenerateQuestionsRequest, user: User = Depends(get_current_user)):
    token = set_provider_fallback_allowed(request.allow_provider_fallback)
    try:
        return await run_billable(user, lambda: exam_service.regenerate_questions(request, actor=user), "question_regeneration")
    finally:
        reset_provider_fallback_allowed(token)


@router.post("/questions/review", response_model=FullExamResponse, tags=["questions"])
async def review_questions(request: ReviewQuestionsRequest, user: User = Depends(get_current_user)):
    """Step 6: Lưu trạng thái duyệt câu hỏi accepted/needs_revision/rejected."""
    return await exam_service.review_questions_from_payload(request, actor=user)


@router.post("/validate", response_model=ValidationResponse, tags=["validation"])
async def validate_exam(request: ValidationRequest):
    return await exam_service.validate_exam(request)


@router.post("/answers/generate", response_model=AnswerGenerateResponse, tags=["answers"])
async def generate_answers(request: AnswerGenerateRequest, user: User = Depends(get_current_user)):
    """Tạo đáp án và rubric cho các câu hỏi đã được giáo viên duyệt."""
    return await run_billable(user, lambda: exam_service.generate_answers(request, actor=user), "answer_generation")


@router.post("/export", tags=["export"])
async def export_docx(request: ExportRequest, user: User = Depends(get_current_user)):
    return await exam_service.export_docx(request.exam_id, actor=user)


@router.get("/templates", tags=["templates"])
async def get_templates():
    return {
        "difficulty_ratio": {"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30},
        "question_types": {
            "multiple_choice": {"enabled": True, "count": 8, "score_per_question": 0.25},
            "true_false": {"enabled": True, "count": 4, "score_per_question": 0.5},
            "short_answer": {"enabled": True, "count": 2, "score_per_question": 0.5},
            "essay": {"enabled": True, "count": 2, "score_per_question": 2.5},
        },
        "supported": {
            "subject": "Khoa học tự nhiên",
            "grade": 8,
            "exam_types": ["Giữa học kì I", "Cuối học kì I", "Giữa học kì II", "Cuối học kì II"],
        },
    }
