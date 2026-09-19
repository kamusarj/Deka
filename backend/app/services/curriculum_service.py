"""Backward-compatible facade for the curriculum service package.

New code should import from ``app.services.curriculum``. This module keeps the
existing import contract stable for integrations that have not migrated yet.
"""

from app.services.curriculum import (
    CURRICULUM_DIR,
    DATA_DIR,
    SUPPORTED_GRADES,
    TEMPLATES_DIR,
    CurriculumNotFoundError,
    CurriculumValidationError,
    _get_curriculum_path,
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
    validate_curriculum_schema,
)

__all__ = [
    "CURRICULUM_DIR",
    "CurriculumNotFoundError",
    "CurriculumValidationError",
    "DATA_DIR",
    "SUPPORTED_GRADES",
    "TEMPLATES_DIR",
    "_get_curriculum_path",
    "get_all_topics",
    "get_exam_scope",
    "get_learning_objectives",
    "get_topic_by_id",
    "get_topics_by_exam_scope",
    "list_available_grades",
    "list_templates",
    "load_curriculum",
    "load_template",
    "validate_all_curriculum_files",
    "validate_curriculum_schema",
]
