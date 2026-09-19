import json

import app.services.curriculum as curriculum
import app.services.curriculum.constants as constants
import app.services.curriculum_service as legacy_curriculum
from app.services.curriculum.errors import CurriculumValidationError


def _valid_curriculum(grade: int = 6) -> dict:
    return {
        "metadata": {
            "subject": "KHTN",
            "grade": grade,
            "curriculum_version": "GDPT 2018",
            "source_type": "local_json",
            "status": "draft",
            "requires_teacher_review": True,
        },
        "topics": [
            {
                "id": "topic_1",
                "learning_objectives": [
                    {"id": "objective_1", "level": "recognition"}
                ],
            }
        ],
        "exam_scopes": [
            {
                "exam_type": "midterm_1",
                "included_topic_ids": ["topic_1"],
                "requires_teacher_review": True,
            }
        ],
    }


def test_legacy_facade_preserves_public_functions():
    assert legacy_curriculum.load_curriculum is curriculum.load_curriculum
    assert legacy_curriculum.validate_curriculum_schema is (
        curriculum.validate_curriculum_schema
    )
    assert legacy_curriculum.load_template is curriculum.load_template


def test_load_curriculum_reports_invalid_json(tmp_path, monkeypatch):
    curriculum_dir = tmp_path / "curriculum"
    curriculum_dir.mkdir()
    (curriculum_dir / "khtn_grade_6.json").write_text("{", encoding="utf-8")
    monkeypatch.setattr(constants, "CURRICULUM_DIR", curriculum_dir)

    try:
        curriculum.load_curriculum(6)
    except CurriculumValidationError as error:
        assert "không phải JSON hợp lệ" in str(error)
    else:
        raise AssertionError("Invalid curriculum JSON must be rejected")


def test_scoped_topics_load_curriculum_once(monkeypatch):
    data = _valid_curriculum()
    calls = 0

    def fake_load_curriculum(grade):
        nonlocal calls
        calls += 1
        assert grade == 6
        return data

    monkeypatch.setattr(
        "app.services.curriculum.catalog.load_curriculum",
        fake_load_curriculum,
    )

    assert curriculum.get_topics_by_exam_scope(6, "midterm_1") == data["topics"]
    assert calls == 1


def test_validation_reports_duplicate_ids_and_invalid_level():
    data = _valid_curriculum()
    duplicate = {
        "id": "objective_1",
        "level": "unsupported",
    }
    data["topics"][0]["learning_objectives"].append(duplicate)

    assert curriculum.validate_curriculum_schema(data) == [
        "Objective id 'objective_1' bị trùng lặp trong topic 'topic_1'",
        "Level 'unsupported' không hợp lệ cho objective 'objective_1'",
    ]


def test_validate_all_files_reports_grade_mismatch(tmp_path, monkeypatch):
    curriculum_dir = tmp_path / "curriculum"
    curriculum_dir.mkdir()
    data = _valid_curriculum(grade=7)
    (curriculum_dir / "khtn_grade_6.json").write_text(
        json.dumps(data),
        encoding="utf-8",
    )
    monkeypatch.setattr(constants, "CURRICULUM_DIR", curriculum_dir)

    results = curriculum.validate_all_curriculum_files()

    assert results[6] == [
        "Grade trong metadata (7) không khớp với tên file (6)"
    ]
    assert all(
        errors and errors[0].startswith("File không tồn tại:")
        for grade, errors in results.items()
        if grade != 6
    )


def test_template_module_handles_valid_and_invalid_json(tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    template_file = templates_dir / "matrix_templates.json"
    template_file.write_text(
        json.dumps({"templates": [{"id": "matrix_1"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(constants, "TEMPLATES_DIR", templates_dir)

    assert curriculum.list_templates("matrix") == [{"id": "matrix_1"}]
    assert curriculum.load_template("matrix", "matrix_1") == {"id": "matrix_1"}

    template_file.write_text("{", encoding="utf-8")
    assert curriculum.list_templates("matrix") == []
    assert curriculum.load_template("matrix", "matrix_1") is None
