import json

from app.services.curriculum.constants import SUPPORTED_GRADES, curriculum_path
from app.services.curriculum.errors import (
    CurriculumNotFoundError,
    CurriculumValidationError,
)
from app.services.curriculum.json_io import read_json
from app.services.curriculum.validation import validate_curriculum_schema


def _get_curriculum_path(grade: int):
    """Backward-compatible private path helper."""
    return curriculum_path(grade)


def load_curriculum(grade: int) -> dict:
    if grade not in SUPPORTED_GRADES:
        raise CurriculumValidationError(
            f"Khối lớp {grade} không được hỗ trợ. "
            f"Chỉ hỗ trợ các khối: {SUPPORTED_GRADES}"
        )

    path = curriculum_path(grade)
    if not path.exists():
        raise CurriculumNotFoundError(
            f"Không tìm thấy file curriculum cho khối {grade}. "
            f"Đường dẫn: {path}"
        )

    try:
        data = read_json(path)
    except json.JSONDecodeError as error:
        raise CurriculumValidationError(
            f"File curriculum khối {grade} không phải JSON hợp lệ: {error}"
        ) from error

    errors = validate_curriculum_schema(data)
    if errors:
        raise CurriculumValidationError(
            f"Curriculum khối {grade} không hợp lệ: {'; '.join(errors)}"
        )

    return data


def list_available_grades() -> list[int]:
    return sorted(
        grade for grade in SUPPORTED_GRADES if curriculum_path(grade).exists()
    )


def _find_exam_scope(curriculum: dict, grade: int, exam_type: str) -> dict:
    exam_scopes = curriculum.get("exam_scopes", [])
    for scope in exam_scopes:
        if scope.get("exam_type") == exam_type:
            return scope

    available_types = [scope.get("exam_type") for scope in exam_scopes]
    raise CurriculumNotFoundError(
        f"Không tìm thấy exam scope '{exam_type}' cho khối {grade}. "
        f"Các loại kiểm tra có sẵn: {available_types}"
    )


def get_exam_scope(grade: int, exam_type: str) -> dict:
    return _find_exam_scope(load_curriculum(grade), grade, exam_type)


def get_topics_by_exam_scope(grade: int, exam_type: str) -> list[dict]:
    curriculum = load_curriculum(grade)
    exam_scope = _find_exam_scope(curriculum, grade, exam_type)
    included_topic_ids = set(exam_scope.get("included_topic_ids", []))
    return [
        topic
        for topic in curriculum.get("topics", [])
        if topic.get("id") in included_topic_ids
    ]


def get_all_topics(grade: int) -> list[dict]:
    return load_curriculum(grade).get("topics", [])


def get_topic_by_id(grade: int, topic_id: str) -> dict | None:
    return next(
        (
            topic
            for topic in load_curriculum(grade).get("topics", [])
            if topic.get("id") == topic_id
        ),
        None,
    )


def get_learning_objectives(grade: int, topic_id: str) -> list[dict]:
    topic = get_topic_by_id(grade, topic_id)
    return topic.get("learning_objectives", []) if topic else []
