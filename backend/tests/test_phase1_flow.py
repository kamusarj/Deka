"""
Phase 1 flow tests.

These tests cover the documented MVP flow: controlled data ingest, normalization,
matrix/spec/question generation, teacher review, answer generation, and validation.
"""

import pytest

from app.schemas.exam import (
    AnswerGenerateRequest,
    DataIngestRequest,
    DataNormalizeRequest,
    FullExamRequest,
    ReviewQuestionsRequest,
    ValidationRequest,
)
from app.services.exam_service import ExamService


def phase1_payload():
    return {
        "school": "THCS Nguyễn Du",
        "grade": 8,
        "subject": "Khoa học tự nhiên",
        "exam_type": "Giữa học kì I",
        "duration_minutes": 45,
        "school_year": "2025-2026",
        "total_score": 10,
        "curriculum": [
            {
                "topic": "Phản ứng hóa học",
                "periods": 10,
                "achievements": [
                    "Trình bày được khái niệm phản ứng hóa học và dấu hiệu nhận biết."
                ],
            },
            {
                "topic": "Mol và tỉ khối chất khí",
                "periods": 12,
                "achievements": ["Tính được khối lượng mol từ công thức hóa học."],
            },
            {
                "topic": "Dung dịch và nồng độ",
                "periods": 8,
                "achievements": ["Tính được nồng độ phần trăm của dung dịch."],
            },
        ],
        "difficulty_ratio": {"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30},
        "question_types": {
            "multiple_choice": {"enabled": True, "count": 8, "score_per_question": 0.25},
            "true_false": {"enabled": True, "count": 4, "score_per_question": 1.0},
            "short_answer": {"enabled": True, "count": 2, "score_per_question": 0.5},
            "essay": {"enabled": True, "count": 2, "score_per_question": 1.5},
        },
    }


def make_service():
    service = ExamService()
    for agent_name in (
        "resource_agent",
        "matrix_agent",
        "spec_agent",
        "question_agent",
        "answer_agent",
        "validator_agent",
        "verification_agent",
    ):
        getattr(service, agent_name).has_ai = False
    return service


@pytest.mark.asyncio
async def test_data_ingest_uses_local_json_source():
    service = make_service()
    result = await service.ingest_data(
        DataIngestRequest(
            grade=8,
            subject="Khoa học tự nhiên",
            exam_type="Giữa học kì I",
        )
    )

    assert result.data_sources[0]["source_type"] == "local_json"
    assert result.data_sources[0]["source_name"] == "khtn_grade_8.json"
    assert result.raw_data["topics"]
    first_topic = result.resource_package["curriculum_suggestions"][0]
    assert first_topic["source"]["source_type"] == "local_json"


@pytest.mark.asyncio
async def test_data_normalize_returns_common_schema_from_manual_plan():
    service = make_service()
    result = await service.normalize_data(
        DataNormalizeRequest(
            grade=8,
            subject="Khoa học tự nhiên",
            exam_type="Giữa học kì I",
            teaching_plan="Phản ứng hóa học (3 tiết)\nMol và tỉ khối chất khí (2 tiết)",
        )
    )

    assert result.normalized_curriculum["grade"] == 8
    assert result.normalized_curriculum["topics"][0]["name"] == "Phản ứng hóa học"
    assert result.total_periods == 5
    assert result.metadata["sources"] == ["local_json"]


@pytest.mark.asyncio
async def test_phase1_full_generation_review_answers_and_validation():
    service = make_service()
    exam = await service.generate_full_exam(FullExamRequest(**phase1_payload()))

    assert exam.id is not None
    assert exam.summary["total_score"] == 10
    assert len(exam.specification) == exam.summary["total_questions"]
    assert len(exam.questions) == exam.summary["total_questions"]
    assert all(question["source"]["source_type"] == "local_json" for question in exam.questions)
    assert exam.validation["passed"] is True

    # Các câu hỏi sinh ra không được trùng nội dung, kể cả khi nhiều câu cùng chủ đề.
    contents = [question["content"].strip().lower() for question in exam.questions]
    assert len(set(contents)) == len(contents), "Đề thi có câu hỏi trùng nội dung"
    duplicate_check = [
        check for check in exam.validation["checks"] if check["name"] == "CHECK_NO_DUPLICATES"
    ][0]
    assert duplicate_check["passed"] is True
    assert exam.validation["warnings"] == []

    accepted_id = exam.questions[0]["id"]
    revision_id = exam.questions[1]["id"]
    rejected_id = exam.questions[2]["id"]
    reviewed = await service.review_questions_from_payload(
        ReviewQuestionsRequest(
            exam_id=exam.id,
            accepted_question_ids=[accepted_id],
            needs_revision_question_ids=[revision_id],
            reviews=[
                {
                    "question_id": rejected_id,
                    "status": "rejected",
                    "comment": "Câu hỏi chưa phù hợp phạm vi đã dạy.",
                    "reviewed_by": "teacher_1",
                }
            ],
        )
    )

    assert reviewed.review_status[accepted_id]["status"] == "accepted"
    assert reviewed.review_status[revision_id]["status"] == "needs_revision"
    assert reviewed.review_status[rejected_id]["status"] == "rejected"
    assert reviewed.review_status[rejected_id]["comment"] == "Câu hỏi chưa phù hợp phạm vi đã dạy."

    answers = await service.generate_answers(
        AnswerGenerateRequest(exam_id=exam.id, accepted_question_ids=[accepted_id])
    )

    assert answers.answer_key[0]["question_id"] == accepted_id


@pytest.mark.asyncio
async def test_validation_fails_when_question_has_no_source_metadata():
    service = make_service()
    exam = await service.generate_full_exam(FullExamRequest(**phase1_payload()))
    questions = [dict(question) for question in exam.questions]
    questions[0].pop("source")

    validation = await service.validate_exam(
        ValidationRequest(
            questions=questions,
            answer_key=exam.answer_key,
            rubric=exam.rubric,
            summary=exam.summary,
            difficulty_ratio=phase1_payload()["difficulty_ratio"],
            total_score=10,
        )
    )

    hallucination_check = [
        check for check in validation.validation["checks"] if check["name"] == "CHECK_NO_HALLUCINATION"
    ][0]
    assert validation.validation["passed"] is False
    assert hallucination_check["passed"] is False
    assert questions[0]["id"] in hallucination_check["actual"]["missing"]
