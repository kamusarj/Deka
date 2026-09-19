"""
Tests cho Curriculum Service.

Test các function trong curriculum_service.py.
"""

import pytest
import sys
import os

# Thêm đường dẫn để import app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.curriculum_service import (
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
    validate_curriculum_schema,
)


# ============================================================
# Test list_available_grades
# ============================================================


class TestListAvailableGrades:
    """Test function list_available_grades."""

    def test_returns_list(self):
        """Kiểm tra trả về list."""
        grades = list_available_grades()
        assert isinstance(grades, list)

    def test_returns_all_grades(self):
        """Kiểm tra trả về đủ 4 khối."""
        grades = list_available_grades()
        assert sorted(grades) == [6, 7, 8, 9]

    def test_returns_sorted(self):
        """Kiểm tra trả về đã sắp xếp."""
        grades = list_available_grades()
        assert grades == sorted(grades)


# ============================================================
# Test load_curriculum
# ============================================================


class TestLoadCurriculum:
    """Test function load_curriculum."""

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_load_valid_grade(self, grade):
        """Kiểm tra load curriculum cho khối hợp lệ."""
        curriculum = load_curriculum(grade)
        assert isinstance(curriculum, dict)
        assert "metadata" in curriculum
        assert "topics" in curriculum
        assert "exam_scopes" in curriculum

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_metadata_grade_matches(self, grade):
        """Kiểm tra grade trong metadata khớp với tên file."""
        curriculum = load_curriculum(grade)
        assert curriculum["metadata"]["grade"] == grade

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_status_is_draft(self, grade):
        """Kiểm tra status là draft."""
        curriculum = load_curriculum(grade)
        assert curriculum["metadata"]["status"] == "draft"

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_requires_teacher_review(self, grade):
        """Kiểm tra requires_teacher_review là true."""
        curriculum = load_curriculum(grade)
        assert curriculum["metadata"]["requires_teacher_review"] is True

    def test_invalid_grade_raises_error(self):
        """Kiểm tra khối lớp không hợp lệ raise lỗi."""
        with pytest.raises(CurriculumValidationError):
            load_curriculum(5)

    def test_invalid_grade_10_raises_error(self):
        """Kiểm tra khối 10 raise lỗi."""
        with pytest.raises(CurriculumValidationError):
            load_curriculum(10)


# ============================================================
# Test get_exam_scope
# ============================================================


class TestGetExamScope:
    """Test function get_exam_scope."""

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_get_midterm_1(self, grade):
        """Kiểm tra lấy exam scope midterm_1."""
        scope = get_exam_scope(grade, "midterm_1")
        assert scope["exam_type"] == "midterm_1"
        assert scope["display_name"] == "Giữa học kì I"

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_get_final_1(self, grade):
        """Kiểm tra lấy exam scope final_1."""
        scope = get_exam_scope(grade, "final_1")
        assert scope["exam_type"] == "final_1"

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_get_fifteen_minutes(self, grade):
        """Kiểm tra lấy exam scope fifteen_minutes."""
        scope = get_exam_scope(grade, "fifteen_minutes")
        assert scope["exam_type"] == "fifteen_minutes"
        assert scope["default_duration_minutes"] == 15

    def test_invalid_exam_type_raises_error(self):
        """Kiểm tra exam type không hợp lệ raise lỗi."""
        with pytest.raises(CurriculumNotFoundError):
            get_exam_scope(8, "invalid_type")

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_requires_teacher_review(self, grade):
        """Kiểm tra exam scope có requires_teacher_review."""
        scope = get_exam_scope(grade, "midterm_1")
        assert scope["requires_teacher_review"] is True

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_default_total_score(self, grade):
        """Kiểm tra tổng điểm mặc định là 10."""
        scope = get_exam_scope(grade, "midterm_1")
        assert scope["default_total_score"] == 10


# ============================================================
# Test get_topics_by_exam_scope
# ============================================================


class TestGetTopicsByExamScope:
    """Test function get_topics_by_exam_scope."""

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_returns_list(self, grade):
        """Kiểm tra trả về list."""
        topics = get_topics_by_exam_scope(grade, "midterm_1")
        assert isinstance(topics, list)

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_topics_have_required_fields(self, grade):
        """Kiểm tra topic có đủ trường bắt buộc."""
        topics = get_topics_by_exam_scope(grade, "midterm_1")
        for topic in topics:
            assert "id" in topic
            assert "name" in topic
            assert "learning_objectives" in topic

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_fifteen_minutes_has_fewer_topics(self, grade):
        """Kiểm tra fifteen_minutes có ít topic hơn midterm."""
        topics_15m = get_topics_by_exam_scope(grade, "fifteen_minutes")
        topics_midterm = get_topics_by_exam_scope(grade, "midterm_1")
        assert len(topics_15m) <= len(topics_midterm)


# ============================================================
# Test get_all_topics
# ============================================================


class TestGetAllTopics:
    """Test function get_all_topics."""

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_returns_list(self, grade):
        """Kiểm tra trả về list."""
        topics = get_all_topics(grade)
        assert isinstance(topics, list)

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_topics_have_ids(self, grade):
        """Kiểm tra topic có id."""
        topics = get_all_topics(grade)
        for topic in topics:
            assert "id" in topic
            assert topic["id"].startswith(f"khtn{grade}_topic_")


# ============================================================
# Test get_topic_by_id
# ============================================================


class TestGetTopicById:
    """Test function get_topic_by_id."""

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_find_existing_topic(self, grade):
        """Kiểm tra tìm topic tồn tại."""
        topics = get_all_topics(grade)
        if topics:
            topic_id = topics[0]["id"]
            result = get_topic_by_id(grade, topic_id)
            assert result is not None
            assert result["id"] == topic_id

    def test_nonexistent_topic_returns_none(self):
        """Kiểm tra tìm topic không tồn tại trả về None."""
        result = get_topic_by_id(8, "nonexistent_topic")
        assert result is None


# ============================================================
# Test get_learning_objectives
# ============================================================


class TestGetLearningObjectives:
    """Test function get_learning_objectives."""

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_returns_list(self, grade):
        """Kiểm tra trả về list."""
        topics = get_all_topics(grade)
        if topics:
            topic_id = topics[0]["id"]
            objectives = get_learning_objectives(grade, topic_id)
            assert isinstance(objectives, list)

    @pytest.mark.parametrize("grade", [6, 7, 8, 9])
    def test_objectives_have_required_fields(self, grade):
        """Kiểm tra objective có đủ trường bắt buộc."""
        topics = get_all_topics(grade)
        if topics:
            topic_id = topics[0]["id"]
            objectives = get_learning_objectives(grade, topic_id)
            for obj in objectives:
                assert "id" in obj
                assert "text" in obj
                assert "level" in obj

    def test_nonexistent_topic_returns_empty(self):
        """Kiểm tra topic không tồn tại trả về list rỗng."""
        objectives = get_learning_objectives(8, "nonexistent_topic")
        assert objectives == []


# ============================================================
# Test validate_curriculum_schema
# ============================================================


class TestValidateCurriculumSchema:
    """Test function validate_curriculum_schema."""

    def test_valid_curriculum_no_errors(self):
        """Kiểm tra curriculum hợp lệ không có lỗi."""
        curriculum = load_curriculum(8)
        errors = validate_curriculum_schema(curriculum)
        assert errors == []

    def test_missing_metadata(self):
        """Kiểm tra thiếu metadata."""
        curriculum = {"topics": [], "exam_scopes": []}
        errors = validate_curriculum_schema(curriculum)
        assert any("metadata" in e.lower() for e in errors)

    def test_wrong_status(self):
        """Kiểm tra status sai."""
        curriculum = {
            "metadata": {
                "subject": "KHTN",
                "grade": 8,
                "curriculum_version": "GDPT 2018",
                "source_type": "local_json",
                "status": "published",  # Sai
                "requires_teacher_review": True,
            },
            "topics": [],
            "exam_scopes": [],
        }
        errors = validate_curriculum_schema(curriculum)
        assert any("draft" in e for e in errors)

    def test_missing_requires_teacher_review(self):
        """Kiểm tra thiếu requires_teacher_review."""
        curriculum = {
            "metadata": {
                "subject": "KHTN",
                "grade": 8,
                "curriculum_version": "GDPT 2018",
                "source_type": "local_json",
                "status": "draft",
                "requires_teacher_review": False,  # Sai
            },
            "topics": [],
            "exam_scopes": [],
        }
        errors = validate_curriculum_schema(curriculum)
        assert any("requires_teacher_review" in e for e in errors)


# ============================================================
# Test validate_all_curriculum_files
# ============================================================


class TestValidateAllCurriculumFiles:
    """Test function validate_all_curriculum_files."""

    def test_returns_dict(self):
        """Kiểm tra trả về dict."""
        results = validate_all_curriculum_files()
        assert isinstance(results, dict)

    def test_all_grades_present(self):
        """Kiểm tra có đủ 4 khối."""
        results = validate_all_curriculum_files()
        assert sorted(results.keys()) == [6, 7, 8, 9]

    def test_all_grades_valid(self):
        """Kiểm tra tất cả khối đều hợp lệ."""
        results = validate_all_curriculum_files()
        for grade, errors in results.items():
            assert errors == [], f"Grade {grade} has errors: {errors}"


# ============================================================
# Test load_template
# ============================================================


class TestLoadTemplate:
    """Test function load_template."""

    def test_load_exam_structure_template(self):
        """Kiểm tra load exam structure template."""
        template = load_template("exam_structure", "khtn_15m_default")
        assert template is not None
        assert template["id"] == "khtn_15m_default"

    def test_load_matrix_template(self):
        """Kiểm tra load matrix template."""
        template = load_template("matrix", "default_midterm_matrix")
        assert template is not None
        assert template["id"] == "default_midterm_matrix"

    def test_load_rubric_template(self):
        """Kiểm tra load rubric template."""
        template = load_template("rubric", "default_essay_rubric")
        assert template is not None
        assert template["id"] == "default_essay_rubric"

    def test_nonexistent_template_returns_none(self):
        """Kiểm tra template không tồn tại trả về None."""
        template = load_template("exam_structure", "nonexistent")
        assert template is None

    def test_invalid_type_returns_none(self):
        """Kiểm tra loại template không hợp lệ trả về None."""
        template = load_template("invalid_type", "khtn_15m_default")
        assert template is None


# ============================================================
# Test list_templates
# ============================================================


class TestListTemplates:
    """Test function list_templates."""

    def test_list_exam_structure_templates(self):
        """Kiểm tra liệt kê exam structure templates."""
        templates = list_templates("exam_structure")
        assert isinstance(templates, list)
        assert len(templates) > 0

    def test_list_matrix_templates(self):
        """Kiểm tra liệt kê matrix templates."""
        templates = list_templates("matrix")
        assert isinstance(templates, list)
        assert len(templates) > 0

    def test_list_rubric_templates(self):
        """Kiểm tra liệt kê rubric templates."""
        templates = list_templates("rubric")
        assert isinstance(templates, list)
        assert len(templates) > 0

    def test_invalid_type_returns_empty(self):
        """Kiểm tra loại không hợp lệ trả về list rỗng."""
        templates = list_templates("invalid_type")
        assert templates == []
