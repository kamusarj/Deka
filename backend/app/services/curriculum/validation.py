import json

from app.services.curriculum.constants import (
    REQUIRED_METADATA_FIELDS,
    SUPPORTED_GRADES,
    VALID_OBJECTIVE_LEVELS,
    curriculum_path,
)
from app.services.curriculum.json_io import read_json


def _validate_metadata(curriculum: dict) -> list[str]:
    errors: list[str] = []
    metadata = curriculum.get("metadata")

    if not metadata:
        return ["Thiếu metadata"]

    for field in REQUIRED_METADATA_FIELDS:
        if field not in metadata:
            errors.append(f"Thiếu metadata.{field}")

    if metadata.get("status") != "draft":
        errors.append(
            f"metadata.status phải là 'draft', hiện tại là '{metadata.get('status')}'"
        )

    if metadata.get("requires_teacher_review") is not True:
        errors.append("metadata.requires_teacher_review phải là true")

    return errors


def _validate_objectives(topic: dict, topic_id: str | None) -> list[str]:
    errors: list[str] = []
    objectives = topic.get("learning_objectives", [])

    if not objectives:
        return [f"Topic '{topic_id}' thiếu learning_objectives"]

    objective_ids: set[str] = set()
    for index, objective in enumerate(objectives):
        objective_id = objective.get("id")
        if not objective_id:
            errors.append(
                f"Thiếu id cho objective thứ {index} trong topic '{topic_id}'"
            )
        elif objective_id in objective_ids:
            errors.append(
                f"Objective id '{objective_id}' bị trùng lặp trong topic '{topic_id}'"
            )
        else:
            objective_ids.add(objective_id)

        level = objective.get("level")
        if level and level not in VALID_OBJECTIVE_LEVELS:
            errors.append(
                f"Level '{level}' không hợp lệ cho objective '{objective_id}'"
            )

    return errors


def _validate_topics(curriculum: dict) -> list[str]:
    topics = curriculum.get("topics")
    if not topics:
        return ["Thiếu topics"]
    if not isinstance(topics, list):
        return ["topics phải là list"]

    errors: list[str] = []
    topic_ids: set[str] = set()
    for index, topic in enumerate(topics):
        topic_id = topic.get("id")
        if not topic_id:
            errors.append(f"Thiếu id cho topic thứ {index}")
        elif topic_id in topic_ids:
            errors.append(f"Topic id '{topic_id}' bị trùng lặp")
        else:
            topic_ids.add(topic_id)

        errors.extend(_validate_objectives(topic, topic_id))

    return errors


def _validate_exam_scopes(curriculum: dict) -> list[str]:
    exam_scopes = curriculum.get("exam_scopes")
    if not exam_scopes:
        return ["Thiếu exam_scopes"]
    if not isinstance(exam_scopes, list):
        return ["exam_scopes phải là list"]

    errors: list[str] = []
    for index, scope in enumerate(exam_scopes):
        scope_type = scope.get("exam_type")
        if not scope_type:
            errors.append(f"Thiếu exam_type cho scope thứ {index}")

        if scope.get("requires_teacher_review") is not True:
            errors.append(
                f"Scope '{scope_type}' thiếu requires_teacher_review = true"
            )

    return errors


def validate_curriculum_schema(curriculum: dict) -> list[str]:
    """Return every schema error while preserving the legacy error order."""
    return [
        *_validate_metadata(curriculum),
        *_validate_topics(curriculum),
        *_validate_exam_scopes(curriculum),
    ]


def validate_all_curriculum_files() -> dict[int, list[str]]:
    results: dict[int, list[str]] = {}

    for grade in SUPPORTED_GRADES:
        path = curriculum_path(grade)
        if not path.exists():
            results[grade] = [f"File không tồn tại: {path}"]
            continue

        try:
            data = read_json(path)
        except json.JSONDecodeError as error:
            results[grade] = [f"JSON không hợp lệ: {error}"]
            continue

        errors = validate_curriculum_schema(data)
        file_grade = data.get("metadata", {}).get("grade")
        if file_grade != grade:
            errors.append(
                f"Grade trong metadata ({file_grade}) "
                f"không khớp với tên file ({grade})"
            )

        results[grade] = errors

    return results
