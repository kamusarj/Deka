"""Phase 2 - Part 2: ngân hàng câu hỏi (không AI)."""

import pytest

from app.schemas.bank_question import BankQuestionCreate, SaveFromExamRequest
from app.schemas.exam import FullExamRequest, ReviewQuestionsRequest
from app.services.exam_service import ExamService
from app.services.question_bank_service import QuestionBankService


def make_exam_service() -> ExamService:
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


def exam_payload():
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
                "achievements": ["Trình bày được khái niệm phản ứng hóa học."],
            },
            {
                "topic": "Dung dịch và nồng độ",
                "periods": 8,
                "achievements": ["Tính được nồng độ phần trăm của dung dịch."],
            },
        ],
        "difficulty_ratio": {"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30},
    }


def sample_question(content="Câu hỏi mẫu về phản ứng hóa học", **overrides):
    payload = {
        "content": content,
        "type": "multiple_choice",
        "difficulty": "nhan_biet",
        "topic": "Phản ứng hóa học",
        "grade": 8,
        "tags": ["phan-ung"],
        "options": [{"key": "A", "text": "Đáp án A"}],
        "answer": {"correct_answer": "A"},
    }
    payload.update(overrides)
    return BankQuestionCreate(**payload)


def test_add_get_delete_question():
    service = QuestionBankService()
    created = service.add_question(sample_question())
    assert created.id is not None
    assert created.usage_count == 0
    assert created.source["source_type"] == "manual_input"

    fetched = service.get_question(created.id)
    assert fetched.content == created.content

    deleted = service.delete_question(created.id)
    assert deleted.deleted is True

    remaining = service.list_questions()
    assert all(question.id != created.id for question in remaining)


def test_list_filters_by_grade_type_and_search():
    service = QuestionBankService()
    keep = service.add_question(
        sample_question("Phản ứng oxi hóa khử là gì", grade=8, type="multiple_choice")
    )
    other_grade = service.add_question(
        sample_question("Câu khối 9 khác biệt", grade=9, type="essay")
    )

    by_grade = service.list_questions(grade=8)
    assert any(question.id == keep.id for question in by_grade)
    assert all(question.id != other_grade.id for question in by_grade)

    by_type = service.list_questions(type="essay")
    assert any(question.id == other_grade.id for question in by_type)

    by_search = service.list_questions(search="oxi hóa khử")
    assert any(question.id == keep.id for question in by_search)
    assert all(question.id != other_grade.id for question in by_search)

    service.delete_question(keep.id)
    service.delete_question(other_grade.id)


def test_bump_usage_increments_count():
    service = QuestionBankService()
    created = service.add_question(sample_question())
    bumped = service.bump_usage(created.id)
    assert bumped.usage_count == 1
    bumped_again = service.bump_usage(created.id)
    assert bumped_again.usage_count == 2
    service.delete_question(created.id)


@pytest.mark.asyncio
async def test_save_from_exam_only_saves_accepted_questions():
    exam_service = make_exam_service()
    exam = await exam_service.generate_full_exam(FullExamRequest(**exam_payload()))
    accepted_id = exam.questions[0]["id"]
    await exam_service.review_questions(
        exam.id,
        ReviewQuestionsRequest(accepted_question_ids=[accepted_id]),
    )

    bank_service = QuestionBankService()
    result = bank_service.save_from_exam(
        SaveFromExamRequest(exam_id=exam.id, tags=["from-exam"])
    )
    assert result.count == 1
    saved = result.saved[0]
    assert saved.source["source_type"] == "question_bank"
    assert "from-exam" in saved.tags
    assert saved.grade == exam.exam_info["grade"]
    assert saved.topic == exam.questions[0]["metadata"]["topic"]
    assert saved.answer["question_id"] == accepted_id
    assert "answer" not in saved.answer
    assert any(
        question.id == saved.id
        for question in bank_service.list_questions(topic=saved.topic)
    )

    # Lưu theo danh sách id tường minh cũng hoạt động.
    explicit = bank_service.save_from_exam(
        SaveFromExamRequest(exam_id=exam.id, question_ids=[exam.questions[1]["id"]])
    )
    assert explicit.count == 1

    for question in result.saved + explicit.saved:
        bank_service.delete_question(question.id)
