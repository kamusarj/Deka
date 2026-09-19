"""Phase 2 - Part 4: xuất đề ra PDF (reportlab, font Unicode tiếng Việt)."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import app
from app.schemas.exam import FullExamRequest
from app.services.pdf_export_service import PdfExportService


def exam_dict():
    """Đề tối thiểu nhưng đủ 4 dạng câu, 1 mã đề — đủ để kiểm tra lộ/không lộ đáp án."""
    variant_questions = [
        {"id": "101_q_1", "number": 1, "type": "multiple_choice", "score": 0.25,
         "content": "Câu trắc nghiệm", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}},
        {"id": "101_q_2", "number": 2, "type": "true_false", "score": 0.5,
         "content": "Câu đúng sai", "statements": [
             {"id": "s1", "content": "Phát biểu một", "is_true": True},
             {"id": "s2", "content": "Phát biểu hai", "is_true": False},
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
         "correct_answer": "Quang hợp diệp lục"},
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


def pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_pdf_has_valid_header():
    pdf_bytes = PdfExportService().create_full_pdf(exam_dict())
    assert pdf_bytes[:4] == b"%PDF"


def test_pdf_contains_written_answers():
    pdf_bytes = PdfExportService().create_full_pdf(exam_dict(), document="answers", variant_code="101")
    text = pdf_text(pdf_bytes)
    assert text.count("Mã đề 101") == 1
    assert "Quang hợp diệp lục" in text
    assert "Học sinh trình bày đúng kiến thức trọng tâm." in text


def test_pdf_accepts_essay_with_null_sub_questions():
    exam = exam_dict()
    exam["variants"][0]["questions"][-1]["sub_questions"] = None

    pdf_bytes = PdfExportService().create_full_pdf(exam, include_answers=False)

    assert "Câu tự luận" in pdf_text(pdf_bytes)


def test_pdf_question_section_does_not_leak_answers():
    pdf_bytes = PdfExportService().create_full_pdf(exam_dict())
    text = pdf_text(pdf_bytes)
    assert "ĐÁP ÁN" not in text  # đề kiểm tra là tài liệu riêng
    question_section = text.split("ĐÁP ÁN")[0]
    # Đáp án trả lời ngắn và đáp án mẫu tự luận không được lộ trong phần đề bài.
    assert "Quang hợp diệp lục" not in question_section
    assert "Học sinh trình bày đúng kiến thức trọng tâm." not in question_section


@pytest.mark.asyncio
async def test_export_pdf_endpoint_returns_pdf(auth_context):
    from app.services.exam_service import ExamService

    service = ExamService()
    for agent_name in (
        "resource_agent", "matrix_agent", "spec_agent",
        "question_agent", "answer_agent", "validator_agent",
        "verification_agent",
    ):
        getattr(service, agent_name).has_ai = False

    exam = await service.generate_full_exam(
        FullExamRequest(
            school="THCS Nguyễn Du", grade=8, subject="Khoa học tự nhiên",
            exam_type="Giữa học kì I", duration_minutes=45, school_year="2025-2026",
            total_score=10,
            curriculum=[{"topic": "Phản ứng hóa học", "periods": 10,
                         "achievements": ["Trình bày được khái niệm phản ứng hóa học."]}],
            difficulty_ratio={"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30},
        ),
        actor=auth_context["user"],
    )

    client = TestClient(app)
    response = client.post(f"/api/exams/{exam.id}/export-pdf", headers=auth_context["headers"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"
    assert "Mã đề" not in pdf_text(response.content)
    for format in ("pdf", "docx"):
        for document in ("exam", "answers", "matrix", "specification"):
            selected = client.post(
                f"/api/exams/{exam.id}/export-{format}",
                params={"document": document, "variant_code": "101"},
                headers=auth_context["headers"],
            )
            assert selected.status_code == 200
            assert f"-{document}-101.{format}" in selected.headers["content-disposition"]
        for params, status in (({"variant_code": "999"}, 404), ({"document": "unknown"}, 422),
                               ({"audience": "student", "document": "answers"}, 422)):
            assert client.post(f"/api/exams/{exam.id}/export-{format}", params=params,
                               headers=auth_context["headers"]).status_code == status
    await service.delete_exam(exam.id, actor=auth_context["user"])
