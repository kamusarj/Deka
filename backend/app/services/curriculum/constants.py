from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[3] / "data"
CURRICULUM_DIR = DATA_DIR / "curriculum"
TEMPLATES_DIR = DATA_DIR / "templates"

SUPPORTED_GRADES = [6, 7, 8, 9]

TEMPLATE_FILES = {
    "exam_structure": "exam_structure_templates.json",
    "matrix": "matrix_templates.json",
    "rubric": "rubric_templates.json",
}

REQUIRED_METADATA_FIELDS = (
    "subject",
    "grade",
    "curriculum_version",
    "source_type",
    "status",
    "requires_teacher_review",
)

VALID_OBJECTIVE_LEVELS = {
    "recognition",
    "understanding",
    "application",
    "high_application",
}


def curriculum_path(grade: int) -> Path:
    return CURRICULUM_DIR / f"khtn_grade_{grade}.json"


def template_path(template_type: str) -> Path | None:
    filename = TEMPLATE_FILES.get(template_type)
    return TEMPLATES_DIR / filename if filename else None
