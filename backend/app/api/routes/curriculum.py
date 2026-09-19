"""
Curriculum API Endpoints

API endpoints để truy cập dữ liệu curriculum local.
Không gọi Gemini API hay bất kỳ AI API nào.

Lưu ý: Đây là seed data, không phải nguồn kiến thức tuyệt đối.
Giáo viên phải luôn xác nhận dữ liệu trước khi tạo ma trận.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth_service import get_current_user
from app.services.curriculum import (
    CurriculumNotFoundError,
    CurriculumValidationError,
    get_all_topics,
    get_exam_scope,
    get_learning_objectives,
    get_topic_by_id,
    get_topics_by_exam_scope,
    list_available_grades,
    list_templates,
    load_curriculum,
    load_template,
    validate_all_curriculum_files,
)

router = APIRouter(
    prefix="/curriculum",
    tags=["curriculum"],
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# Response Models
# ============================================================


class ErrorResponse(BaseModel):
    """Response model cho lỗi."""
    detail: str


class GradeListResponse(BaseModel):
    """Response model cho danh sách khối lớp."""
    grades: list[int]


class ValidationResponse(BaseModel):
    """Response model cho kết quả validation."""
    results: dict[int, list[str]]
    total_errors: int
    all_valid: bool


class TemplateListResponse(BaseModel):
    """Response model cho danh sách template."""
    templates: list[dict]


# ============================================================
# Endpoints
# ============================================================


@router.get(
    "/grades",
    response_model=GradeListResponse,
    summary="Liệt kê các khối lớp có sẵn curriculum",
    description="Trả về danh sách các khối lớp (6, 7, 8, 9) có file curriculum."
)
async def get_grades():
    """Liệt kê các khối lớp có sẵn curriculum."""
    grades = list_available_grades()
    return GradeListResponse(grades=grades)


@router.get(
    "/{grade}",
    summary="Lấy toàn bộ curriculum theo khối lớp",
    description="Trả về toàn bộ dữ liệu curriculum cho một khối lớp cụ thể."
)
async def get_curriculum(grade: int):
    """Lấy toàn bộ curriculum theo khối lớp."""
    try:
        curriculum = load_curriculum(grade)
        return curriculum
    except CurriculumNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CurriculumValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{grade}/exam-scopes",
    summary="Lấy danh sách exam scopes theo khối lớp",
    description="Trả về danh sách các loại kiểm tra có sẵn cho một khối lớp."
)
async def get_exam_scopes(grade: int):
    """Lấy danh sách exam scopes theo khối lớp."""
    try:
        curriculum = load_curriculum(grade)
        exam_scopes = curriculum.get("exam_scopes", [])
        return {"grade": grade, "exam_scopes": exam_scopes}
    except CurriculumNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CurriculumValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{grade}/exam-scopes/{exam_type}",
    summary="Lấy thông tin exam scope cụ thể",
    description="Trả về thông tin chi tiết của một loại kiểm tra cụ thể."
)
async def get_exam_scope_detail(grade: int, exam_type: str):
    """Lấy thông tin exam scope cụ thể."""
    try:
        scope = get_exam_scope(grade, exam_type)
        return scope
    except CurriculumNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CurriculumValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{grade}/exam-scopes/{exam_type}/topics",
    summary="Lấy danh sách topic theo exam scope",
    description="Trả về danh sách các topic thuộc một loại kiểm tra cụ thể."
)
async def get_topics_by_scope(grade: int, exam_type: str):
    """Lấy danh sách topic theo exam scope."""
    try:
        topics = get_topics_by_exam_scope(grade, exam_type)
        return {
            "grade": grade,
            "exam_type": exam_type,
            "topics": topics,
            "total_topics": len(topics),
        }
    except CurriculumNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CurriculumValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{grade}/topics",
    summary="Lấy tất cả topic theo khối lớp",
    description="Trả về tất cả các topic của một khối lớp."
)
async def get_all_topics_endpoint(grade: int):
    """Lấy tất cả topic theo khối lớp."""
    try:
        topics = get_all_topics(grade)
        return {
            "grade": grade,
            "topics": topics,
            "total_topics": len(topics),
        }
    except CurriculumNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CurriculumValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{grade}/topics/{topic_id}",
    summary="Lấy thông tin topic theo ID",
    description="Trả về thông tin chi tiết của một topic cụ thể."
)
async def get_topic_detail(grade: int, topic_id: str):
    """Lấy thông tin topic theo ID."""
    try:
        topic = get_topic_by_id(grade, topic_id)
        if topic is None:
            raise HTTPException(
                status_code=404,
                detail=f"Không tìm thấy topic '{topic_id}' trong khối {grade}"
            )
        return topic
    except CurriculumNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CurriculumValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{grade}/topics/{topic_id}/objectives",
    summary="Lấy learning objectives theo topic",
    description="Trả về danh sách learning objectives của một topic."
)
async def get_objectives(grade: int, topic_id: str):
    """Lấy learning objectives theo topic."""
    try:
        objectives = get_learning_objectives(grade, topic_id)
        return {
            "grade": grade,
            "topic_id": topic_id,
            "objectives": objectives,
            "total_objectives": len(objectives),
        }
    except CurriculumNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CurriculumValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/validate/all",
    response_model=ValidationResponse,
    summary="Validate tất cả file curriculum",
    description="Kiểm tra tính hợp lệ của tất cả file curriculum."
)
async def validate_all():
    """Validate tất cả file curriculum."""
    results = validate_all_curriculum_files()
    total_errors = sum(len(errors) for errors in results.values())
    all_valid = total_errors == 0
    return ValidationResponse(
        results=results,
        total_errors=total_errors,
        all_valid=all_valid,
    )


# ============================================================
# Template Endpoints
# ============================================================


@router.get(
    "/templates/{template_type}",
    response_model=TemplateListResponse,
    summary="Liệt kê templates theo loại",
    description="Trả về danh sách templates theo loại (exam_structure, matrix, rubric)."
)
async def get_templates(template_type: str):
    """Liệt kê templates theo loại."""
    valid_types = ["exam_structure", "matrix", "rubric"]
    if template_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Loại template '{template_type}' không hợp lệ. "
                   f"Các loại hợp lệ: {valid_types}"
        )
    templates = list_templates(template_type)
    return TemplateListResponse(templates=templates)


@router.get(
    "/templates/{template_type}/{template_id}",
    summary="Lấy template theo ID",
    description="Trả về thông tin chi tiết của một template cụ thể."
)
async def get_template_detail(template_type: str, template_id: str):
    """Lấy template theo ID."""
    valid_types = ["exam_structure", "matrix", "rubric"]
    if template_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Loại template '{template_type}' không hợp lệ. "
                   f"Các loại hợp lệ: {valid_types}"
        )
    template = load_template(template_type, template_id)
    if template is None:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy template '{template_id}' "
                   f"trong loại '{template_type}'"
        )
    return template
