"""Persistence contract for real-AI output rejected after generation."""

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.agents.verification_agent import VerificationAgent
from app.api.routes import mvp_flow
from app.core.database import get_session_factory
from app.models.exam import Exam
from app.schemas.bank_question import SaveFromExamRequest
from app.schemas.exam import FullExamRequest, RegenerateQuestionsRequest
from app.services.ai_provider_chain import provider_fallback_allowed
from app.services.exam_service import ExamService
from app.services.question_bank_service import QuestionBankService


def request_payload(*, allow_provider_fallback: bool) -> FullExamRequest:
    return FullExamRequest(
        school="THCS Nguyễn Du",
        grade=8,
        subject="Khoa học tự nhiên",
        exam_type="Giữa học kì I",
        duration_minutes=45,
        school_year="2026-2027",
        total_score=10,
        curriculum=[
            {
                "topic": "Hệ tuần hoàn ở người",
                "periods": 6,
                "achievements": ["Mô tả được cấu tạo và chức năng của tim người."],
            }
        ],
        difficulty_ratio={"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30},
        variant_count=1,
        allow_provider_fallback=allow_provider_fallback,
    )


SPECIFICATION = [
    {
        "question_id": "q_1",
        "question_number": 1,
        "question_type": "multiple_choice",
        "difficulty": "nhan_biet",
        "score": 10,
        "topic": "Hệ tuần hoàn ở người",
        "lesson": "Tim người",
        "knowledge_unit": "Chức năng của tim",
        "achievement": "Mô tả được cấu tạo và chức năng của tim người.",
    }
]


def generated_payload(content: str) -> dict:
    return {
        "questions": [
            {
                "id": "q_1",
                "number": 1,
                "type": "multiple_choice",
                "difficulty": "nhan_biet",
                "score": 10,
                "content": content,
                "options": {
                    "A": "Bơm máu đi khắp cơ thể",
                    "B": "Trao đổi khí trực tiếp",
                    "C": "Tiêu hóa thức ăn",
                    "D": "Lọc chất thải khỏi máu",
                },
                "correct_answer": "A",
                "metadata": {
                    "topic": "Hệ tuần hoàn ở người",
                    "lesson": "Tim người",
                    "knowledge_unit": "Chức năng của tim",
                    "achievement": "Mô tả được cấu tạo và chức năng của tim người.",
                    "bloom_level": "remember",
                },
            }
        ],
        "answer_key": [
            {
                "question_id": "q_1",
                "question_number": 1,
                "type": "multiple_choice",
                "correct_answer": "A",
                "explanation": "Tim co bóp tạo lực đẩy máu qua hệ mạch.",
                "option_explanations": {
                    "A": "Đúng vì tim tạo lực đẩy máu.",
                    "B": "Sai vì trao đổi khí diễn ra chủ yếu ở phổi.",
                    "C": "Sai vì tiêu hóa thuộc hệ tiêu hóa.",
                    "D": "Sai vì lọc máu là chức năng của thận.",
                },
            }
        ],
        "rubric": [],
    }


def verification_report(*, approved: bool) -> dict:
    status = "approved" if approved else "not_verified"
    solve_status = "match" if approved else "skipped"
    return {
        "overall_score": 100 if approved else None,
        "overall_status": "passed" if approved else "not_verified",
        "summary": {
            "total_questions": 1,
            "auto_approved": 1 if approved else 0,
            "needs_review": 0,
            "auto_rejected": 0,
            "not_verified": 0 if approved else 1,
        },
        "question_reports": [
            {
                "question_id": "q_1",
                "question_number": 1,
                "verification_score": 100 if approved else None,
                "status": status,
                "checks": {
                    "solve_compare": {
                        "status": solve_status,
                        "multiple_correct": False,
                    }
                },
                "issues": [],
            }
        ],
        "action_required": [],
    }


def quality_failure_report() -> dict:
    report = verification_report(approved=True)
    report["overall_score"] = 70
    report["overall_status"] = "passed_with_warnings"
    report["summary"].update(auto_approved=0, needs_review=1)
    report["question_reports"][0].update(
        verification_score=70,
        status="needs_review",
        issues=[
            {
                "severity": "critical",
                "type": "learning_objective_copy",
                "description": "Yêu cầu cần đạt bị dùng như nội dung đáp án.",
                "suggestion": "Viết lại bằng quan hệ khoa học cụ thể.",
            }
        ],
    )
    return report


class GeneratedContentAgent:
    has_ai = True

    def __init__(self, outputs: list[dict]):
        self.outputs = outputs
        self.calls: list[dict] = []

    async def run(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        return deepcopy(self.outputs.pop(0))


class ReviewerAgent:
    def __init__(self, reports: list[dict]):
        self.reports = reports
        self.calls: list[dict] = []

    async def run(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        return deepcopy(self.reports.pop(0))

    async def run_with_progress(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        yield "Đã kiểm chứng 1/1 câu (câu 1)", None
        yield None, deepcopy(self.reports.pop(0))

    @staticmethod
    def hard_failure_reasons(report, *, require_independent=False):
        return VerificationAgent.hard_failure_reasons(
            report, require_independent=require_independent
        )

    @staticmethod
    def reviewer_summary(_reports):
        return None


def build_service(*, generated: list[dict], reports: list[dict]) -> ExamService:
    service = ExamService()
    service.resource_agent.run = AsyncMock(
        return_value={"data_sources": [], "raw_data": {}, "curriculum_suggestions": []}
    )
    service.matrix_agent.run = AsyncMock(
        return_value={
            "matrix": [],
            "summary": {"total_score": 10, "expected_ratio": {}},
            "question_plan": [],
        }
    )
    service.spec_agent.run = AsyncMock(return_value=deepcopy(SPECIFICATION))
    service.question_agent = GeneratedContentAgent(generated)
    service.validator_agent.run = AsyncMock(
        return_value={
            "passed": True,
            "score": 100,
            "checks": [],
            "warnings": [],
            "errors": [],
        }
    )
    service.verification_agent = ReviewerAgent(reports)
    service._apply_rag_sources = lambda specification, **_kwargs: specification
    return service


@pytest.mark.asyncio
async def test_regeneration_rejects_mixed_unknown_ids_before_provider_work(auth_context):
    service = build_service(
        generated=[generated_payload("Original"), generated_payload("Replacement")],
        reports=[verification_report(approved=True), verification_report(approved=True)],
    )
    user = auth_context["user"]
    exam = await service.generate_full_exam(request_payload(allow_provider_fallback=False), actor=user)
    try:
        calls = len(service.question_agent.calls)
        with pytest.raises(HTTPException) as error:
            await service.regenerate_questions(RegenerateQuestionsRequest(
                exam_id=exam.id, question_ids=["q_1", "q_unknown"], allow_provider_fallback=False,
            ), actor=user)
        assert error.value.status_code == 400
        assert len(service.question_agent.calls) == calls
        unchanged = await service.get_exam(exam.id, actor=user)
        assert unchanged.questions == exam.questions
        assert unchanged.review_status == exam.review_status
    finally:
        await service.delete_exam(exam.id, actor=user)


@pytest.mark.asyncio
async def test_primary_only_failure_persists_owned_non_publishable_draft(auth_context):
    service = build_service(
        generated=[generated_payload("Nội dung thật từ provider")],
        reports=[verification_report(approved=False)],
    )
    user = auth_context["user"]

    draft = await service.generate_full_exam(
        request_payload(allow_provider_fallback=False), actor=user
    )
    try:
        assert draft.id is not None
        assert draft.owner_user_id == user.id
        assert draft.publication_status == "draft"
        assert draft.questions[0]["content"] == "Nội dung thật từ provider"
        assert draft.variants == []
        persistence = draft.validation["persistence"]
        assert persistence["status"] == "draft"
        assert persistence["publishable"] is False
        assert persistence["failure_stage"] == "semantic_verification"
        assert "Nội dung AI đã được lưu dưới dạng bản nháp" in persistence["message"]
        assert "DeepSeek V4 Pro" in persistence["gate_message"]
        assert persistence["question_failures"] == {
            "q_1": ["semantic_review_unavailable"]
        }
        assert persistence["errors"] == []
        assert len(service.question_agent.calls) == 1

        with pytest.raises(HTTPException) as export_error:
            await service.export_docx(draft.id, actor=user)
        assert export_error.value.status_code == 409

        with pytest.raises(HTTPException) as bank_error:
            QuestionBankService().save_from_exam(
                SaveFromExamRequest(exam_id=draft.id, question_ids=["q_1"]),
                actor=user,
            )
        assert bank_error.value.status_code == 409
    finally:
        await service.delete_exam(draft.id, actor=user)


@pytest.mark.asyncio
async def test_legacy_or_fallback_request_keeps_fail_before_persistence(auth_context):
    service = build_service(
        generated=[generated_payload("Không được lưu")],
        reports=[verification_report(approved=False)],
    )
    user = auth_context["user"]
    with get_session_factory()() as db:
        before = db.query(Exam).filter(Exam.owner_user_id == user.id).count()

    with pytest.raises(HTTPException) as error:
        await service.generate_full_exam(
            request_payload(allow_provider_fallback=True), actor=user
        )

    assert error.value.status_code == 503
    with get_session_factory()() as db:
        after = db.query(Exam).filter(Exam.owner_user_id == user.id).count()
    assert after == before


@pytest.mark.asyncio
async def test_exhausted_automatic_repair_saves_latest_real_payload_once(auth_context):
    service = build_service(
        generated=[
            generated_payload("Nội dung thật trước auto-repair"),
            generated_payload("Nội dung thật mới nhất sau auto-repair"),
        ],
        reports=[quality_failure_report(), quality_failure_report()],
    )
    user = auth_context["user"]

    draft = await service.generate_full_exam(
        request_payload(allow_provider_fallback=False), actor=user
    )
    try:
        assert draft.publication_status == "draft"
        assert draft.questions[0]["content"] == (
            "Nội dung thật mới nhất sau auto-repair"
        )
        assert draft.validation["persistence"]["question_failures"] == {
            "q_1": ["learning_objective_copy"]
        }
        assert draft.review_status["q_1"]["regenerated"] is True
        assert len(service.question_agent.calls) == 2
        assert len(service.verification_agent.calls) == 2
    finally:
        await service.delete_exam(draft.id, actor=user)


@pytest.mark.asyncio
async def test_sse_returns_saved_draft_result_instead_of_error(auth_context):
    service = build_service(
        generated=[generated_payload("Nội dung SSE thật")],
        reports=[verification_report(approved=False)],
    )
    user = auth_context["user"]
    events = [
        event
        async for event in service.generate_full_exam_stream(
            request_payload(allow_provider_fallback=False), actor=user
        )
    ]
    payload = "".join(events)
    try:
        assert '"publication_status": "draft"' in payload
        assert '"stage": "build_variants", "status": "skipped"' in payload
        assert '"stage": "error"' not in payload
        drafts = await service.list_exams(actor=user)
        assert any(item.publication_status == "draft" for item in drafts)
    finally:
        drafts = await service.list_exams(actor=user)
        for item in drafts:
            if item.publication_status == "draft":
                await service.delete_exam(item.id, actor=user)


@pytest.mark.asyncio
async def test_draft_retry_is_no_fallback_selected_only_and_promotes_same_row(auth_context):
    service = build_service(
        generated=[
            generated_payload("Nội dung cần sửa"),
            generated_payload("Nội dung đã sửa và kiểm định"),
        ],
        reports=[
            verification_report(approved=False),
            verification_report(approved=True),
        ],
    )
    user = auth_context["user"]
    draft = await service.generate_full_exam(
        request_payload(allow_provider_fallback=False), actor=user
    )
    try:
        with pytest.raises(HTTPException) as fallback_error:
            await service.regenerate_questions(
                RegenerateQuestionsRequest(
                    exam_id=draft.id,
                    question_ids=["q_1"],
                    reason="Sửa lỗi kiểm định",
                ),
                actor=user,
            )
        assert fallback_error.value.status_code == 400
        assert len(service.question_agent.calls) == 1

        service.verification_agent.calls.clear()
        repaired = await service.regenerate_questions(
            RegenerateQuestionsRequest(
                exam_id=draft.id,
                question_ids=["q_1"],
                reason="Sửa lỗi kiểm định",
                allow_provider_fallback=False,
            ),
            actor=user,
        )

        assert repaired.id == draft.id
        assert repaired.publication_status == "verified"
        assert repaired.questions[0]["content"] == "Nội dung đã sửa và kiểm định"
        assert len(repaired.variants) == 1
        assert [item["question_id"] for item in service.question_agent.calls[-1]["specification"]] == ["q_1"]
        assert [item["id"] for item in service.verification_agent.calls[0]["questions"]] == ["q_1"]
        assert repaired.validation["persistence"] == {
            "status": "verified",
            "publishable": True,
        }
    finally:
        await service.delete_exam(draft.id, actor=user)


@pytest.mark.asyncio
async def test_regeneration_route_applies_request_scoped_no_fallback(
    auth_context, monkeypatch
):
    observed: list[bool] = []

    async def inspect_policy(_request, actor=None):
        observed.append(provider_fallback_allowed())
        return {"actor_id": actor.id}

    monkeypatch.setattr(mvp_flow.exam_service, "regenerate_questions", inspect_policy)
    request = RegenerateQuestionsRequest(
        exam_id=123,
        question_ids=["q_1"],
        reason="Sửa câu lỗi",
        allow_provider_fallback=False,
    )

    result = await mvp_flow.regenerate_questions(
        request, user=auth_context["user"]
    )

    assert result == {"actor_id": auth_context["user"].id}
    assert observed == [False]
    assert provider_fallback_allowed() is True
