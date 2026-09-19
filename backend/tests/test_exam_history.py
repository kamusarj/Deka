"""Phase 2 - Part 5: quản lý lịch sử đề (delete, duplicate, filter/paginate)."""

import pytest
from fastapi import HTTPException

from app.schemas.exam import FullExamRequest, ReviewQuestionsRequest
from app.services.exam_service import ExamService


def make_service() -> ExamService:
    service = ExamService()
    for agent_name in (
        "resource_agent", "matrix_agent", "spec_agent",
        "question_agent", "answer_agent", "validator_agent",
        "verification_agent",
    ):
        getattr(service, agent_name).has_ai = False
    return service


def payload(grade=8, exam_type="Giữa học kì I"):
    return {
        "school": "THCS Nguyễn Du",
        "grade": grade,
        "subject": "Khoa học tự nhiên",
        "exam_type": exam_type,
        "duration_minutes": 45,
        "school_year": "2025-2026",
        "total_score": 10,
        "curriculum": [
            {"topic": "Phản ứng hóa học", "periods": 10,
             "achievements": ["Trình bày được khái niệm phản ứng hóa học."]},
            {"topic": "Dung dịch và nồng độ", "periods": 8,
             "achievements": ["Tính được nồng độ phần trăm của dung dịch."]},
        ],
        "difficulty_ratio": {"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30},
    }


@pytest.mark.asyncio
async def test_delete_exam_removes_it():
    service = make_service()
    exam = await service.generate_full_exam(FullExamRequest(**payload()))
    result = await service.delete_exam(exam.id)
    assert result.deleted is True
    with pytest.raises(HTTPException) as error:
        await service.get_exam(exam.id)
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_exam_new_id_same_content_reset_review():
    service = make_service()
    exam = await service.generate_full_exam(FullExamRequest(**payload()))
    accepted_id = exam.questions[0]["id"]
    await service.review_questions(
        exam.id, ReviewQuestionsRequest(accepted_question_ids=[accepted_id])
    )

    duplicate = await service.duplicate_exam(exam.id)
    try:
        assert duplicate.id != exam.id
        # Nội dung câu hỏi giống hệt.
        assert [q["content"] for q in duplicate.questions] == [q["content"] for q in exam.questions]
        assert duplicate.matrix == exam.matrix
        # Trạng thái duyệt được reset về pending.
        assert all(status["status"] == "pending" for status in duplicate.review_status.values())
        assert len(duplicate.review_status) == len(duplicate.questions)
    finally:
        await service.delete_exam(duplicate.id)
        await service.delete_exam(exam.id)


@pytest.mark.asyncio
async def test_list_exams_filters_by_grade_and_exam_type():
    service = make_service()
    exam_g8 = await service.generate_full_exam(FullExamRequest(**payload(grade=8)))
    exam_g9 = await service.generate_full_exam(
        FullExamRequest(**payload(grade=9, exam_type="Cuối học kì I"))
    )
    try:
        by_grade = await service.list_exams(grade=9)
        ids = {exam.id for exam in by_grade}
        assert exam_g9.id in ids
        assert exam_g8.id not in ids

        by_type = await service.list_exams(exam_type="Cuối học kì I")
        type_ids = {exam.id for exam in by_type}
        assert exam_g9.id in type_ids
        assert exam_g8.id not in type_ids

        limited = await service.list_exams(limit=1)
        assert len(limited) == 1
    finally:
        await service.delete_exam(exam_g8.id)
        await service.delete_exam(exam_g9.id)
