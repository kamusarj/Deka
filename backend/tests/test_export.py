"""Tests for Word export (ExportService) and the /api/export endpoint."""

from io import BytesIO
from copy import deepcopy

import pytest
from docx import Document
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import app
from app.services.export_service import ExportService
from app.services.pdf_export_service import PdfExportService
from app.services.exam.export_document import select_export_data


def _exam_dict():
    """A minimal but complete exam dict with all four question types and 2 variants."""
    variant_questions = [
        {"id": "101_q_1", "number": 1, "type": "multiple_choice", "score": 0.25,
         "content": "Câu trắc nghiệm", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}},
        {"id": "101_q_2", "number": 2, "type": "true_false", "score": 0.5,
         "content": "Câu đúng sai", "statements": [
             {"id": "s1", "content": "P1", "is_true": True},
             {"id": "s2", "content": "P2", "is_true": False},
         ]},
        {"id": "101_q_3", "number": 3, "type": "short_answer", "score": 0.5,
         "content": "Câu trả lời ngắn"},
        {"id": "101_q_4", "number": 4, "type": "essay", "score": 2.5,
         "content": "Câu tự luận", "sub_questions": [{"id": "sub", "content": "Ý a", "score": 1.5}]},
    ]
    variant_answers = [
        {"question_id": "101_q_1", "question_number": 1, "type": "multiple_choice", "correct_answer": "A"},
        {"question_id": "101_q_2", "question_number": 2, "type": "true_false",
         "answers": [{"statement_id": "s1", "is_true": True}, {"statement_id": "s2", "is_true": False}]},
        {"question_id": "101_q_3", "question_number": 3, "type": "short_answer",
         "correct_answer": "Phản ứng hóa học"},
        {"question_id": "101_q_4", "question_number": 4, "type": "essay",
         "model_answer": "Học sinh trình bày đúng kiến thức trọng tâm."},
    ]
    return {
        "exam_info": {"school": "THCS X", "grade": 8, "subject": "Khoa học tự nhiên",
                      "exam_type": "Giữa học kì I", "school_year": "2025-2026",
                      "duration_minutes": 45, "total_score": 10, "variant_count": 1},
        "matrix": [{"lesson_name": "Bài 1",
                    "nhan_biet": {"count": 1, "score": 0.25},
                    "thong_hieu": {"count": 1, "score": 0.5},
                    "van_dung": {"count": 2, "score": 3.0},
                    "total_score": 3.75}],
        "summary": {"total_score": 10, "total_questions": 4},
        "specification": [{"question_number": 1, "knowledge_unit": "KT", "achievement": "YC",
                           "difficulty": "nhan_biet", "question_type": "multiple_choice", "score": 0.25}],
        "questions": variant_questions, "answer_key": variant_answers,
        "rubric": [{"question_number": 4, "total_score": 2.5, "criteria": [
            {"name": "Nội dung", "max_score": 2.5, "levels": [{"score": 2.5, "description": "Đủ ý"}]}]}],
        "variants": [{"code": "101", "questions": variant_questions, "answer_key": variant_answers}],
    }


def _docx_text(document) -> str:
    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    doc = Document(buffer)
    return "\n".join(p.text for p in doc.paragraphs)


def test_variant_answers_include_written_answers():
    """Đáp án trả lời ngắn và tự luận phải xuất hiện trong file Word theo mã đề."""
    document = ExportService().create_full_docx(_exam_dict(), document="answers", variant_code="101")
    text = _docx_text(document)
    assert text.count("Mã đề 101") == 1
    # Short-answer correct answer and essay model answer must both appear.
    assert "Phản ứng hóa học" in text
    assert "Học sinh trình bày đúng kiến thức trọng tâm." in text


def test_student_export_omits_answers_and_rubric():
    document = ExportService().create_full_docx(_exam_dict(), include_answers=False)
    text = _docx_text(document)
    assert "Câu trắc nghiệm" in text
    assert "Đáp án" not in text
    assert "Hướng dẫn chấm" not in text
    assert "Phản ứng hóa học" not in text


def test_export_accepts_essay_with_null_sub_questions():
    exam = _exam_dict()
    exam["variants"][0]["questions"][-1]["sub_questions"] = None

    document = ExportService().create_full_docx(exam, include_answers=False)

    assert "Câu tự luận" in _docx_text(document)


def test_export_does_not_leak_answers_in_question_body():
    """Phần đề bài không được lộ đáp án (không có 'Đ'/'S' hay đáp án đúng)."""
    document = ExportService().create_full_docx(_exam_dict())
    text = _docx_text(document)
    question_section = text.split("IV. Đáp án")[0]
    assert "is_true" not in question_section


def test_export_endpoint_rejects_bad_input(auth_context):
    """POST /api/export trả 422 thay vì 500 khi thiếu/sai exam_id."""
    client = TestClient(app)
    assert client.post("/api/export", json={}, headers=auth_context["headers"]).status_code == 422
    assert client.post("/api/export", json={"exam_id": "abc"}, headers=auth_context["headers"]).status_code == 422


def render_text(format, data, **options):
    if format == "pdf":
        content = PdfExportService().create_full_pdf(data, **options)
        return "\n".join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)
    doc = ExportService().create_full_docx(data, **options)
    return "\n".join([
        *(p.text for p in doc.paragraphs),
        *(cell.text for table in doc.tables for row in table.rows for cell in row.cells),
    ])


@pytest.mark.parametrize("format", ["docx", "pdf"])
@pytest.mark.parametrize("document,present,absent", [
    ("exam", "Câu trắc nghiệm", ["Phản ứng hóa học", "Đủ ý", "Bài 1", "YC"]),
    ("answers", "Phản ứng hóa học", ["Câu trắc nghiệm", "Bài 1", "YC"]),
    ("matrix", "Bài 1", ["Câu trắc nghiệm", "Phản ứng hóa học", "YC"]),
    ("specification", "YC", ["Câu trắc nghiệm", "Phản ứng hóa học", "Bài 1"]),
])
def test_exports_contain_only_the_requested_document(format, document, present, absent):
    data = _exam_dict()
    before = deepcopy(data)
    text = render_text(format, data, document=document, variant_code="101")
    assert present in text
    assert all(value not in text for value in absent)
    assert text.count("Mã đề 101") == 1
    assert data == before


@pytest.mark.parametrize("format", ["docx", "pdf"])
def test_export_selects_one_paper_and_places_code_before_questions(format):
    data = _exam_dict()
    second = deepcopy(data["variants"][0])
    second["code"] = "102"
    second["questions"][0]["content"] = "Câu hỏi riêng bản 102"
    data["variants"].append(second)
    text = render_text(format, data, variant_code="102", include_answers=False)
    assert text.count("Mã đề 102") == 1
    assert text.index("Mã đề 102") < text.index("Câu 1")
    assert "Câu hỏi riêng bản 102" in text
    assert "Mã đề 101" not in text and "Câu trắc nghiệm" not in text
    original = render_text(format, data)
    assert "Bản gốc" in original and "Câu trắc nghiệm" in original
    assert "Mã đề" not in original and "Câu hỏi riêng bản 102" not in original
    with pytest.raises(HTTPException) as error:
        render_text(format, data, variant_code="999")
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        render_text(format, data, document="answers", include_answers=False)
    assert error.value.status_code == 422


def test_selected_paper_remaps_specification_and_rubric_without_mutation():
    data = _exam_dict()
    data["variants"][0]["questions"][0].update(original_id="q_mc", original_number=1, number=4)
    data["specification"][0]["question_id"] = "q_mc"
    data["rubric"][0].update(question_id="q_mc", question_number=1)
    selected = select_export_data(data, "101")
    assert selected["specification"][0]["question_number"] == 4
    assert selected["rubric"][0]["question_number"] == 4
    assert data["specification"][0]["question_number"] == 1
