from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.agents.verification_agent import VerificationAgent
from app.core.config import settings
from app.schemas.ai_outputs import IndependentVerificationOutput
from app.services.ai_provider_chain import (
    reset_provider_fallback_allowed,
    set_provider_fallback_allowed,
)
from app.services.dual_verification_service import DualVerificationService, Reviewer
from app.services.exam_service import ExamService


def question():
    return {
        "id": "q_1",
        "number": 1,
        "type": "multiple_choice",
        "difficulty": "nhan_biet",
        "content": "Tim người có bao nhiêu ngăn?",
        "options": {"A": "2", "B": "3", "C": "4", "D": "5"},
        "metadata": {
            "topic": "Hệ tuần hoàn",
            "achievement": "Mô tả được cấu tạo tim",
        },
    }


def review_payload(*, answer="C", assessed_difficulty="nhan_biet", answer_correct=True):
    return {
        "solve": {
            "your_answer": answer,
            "statement_answers": [],
            "multiple_correct": False,
            "confidence": 0.95,
            "reasoning": "Tim người có bốn ngăn.",
            "detected_issues": [],
        },
        "quality": {
            "is_valid": True,
            "knowledge_target": "Cấu tạo tim người",
            "source_grounded": True,
            "objective_copied": False,
            "answer_correct": answer_correct,
            "single_correct_answer": True,
            "explanation_scientific": True,
            "required_context_present": True,
            "issues_found": [],
            "distractors": [],
            "overall_distractor_quality": "good",
            "statements": [],
            "assessed_difficulty": assessed_difficulty,
            "difficulty_matches": assessed_difficulty == "nhan_biet",
            "reasoning": "Câu hỏi phù hợp.",
        },
    }


def reviewer_result(key, payload):
    identities = {
        "deepseek": ("DeepSeek V4 Pro", "deepseek", "deepseek-v4-pro"),
        "gemini": ("Gemini 3.7 Flash", "gemini", "gemini-3.7-flash"),
    }
    label, provider, model = identities[key]
    return {
        "label": label,
        "provider": provider,
        "model": model,
        "result": payload,
    }


class FakeDualReviewers:
    mode = "dual"

    def __init__(self, deepseek=None, gemini=None, *, available=True):
        self.is_available = available
        self.payloads = {
            "deepseek": deepseek or review_payload(),
            "gemini": gemini or review_payload(),
        }
        self.calls = 0

    def available(self):
        return self.is_available

    async def review(self, _prompt, *, response_model):
        assert response_model is IndependentVerificationOutput
        self.calls += 1
        return {
            key: reviewer_result(key, payload)
            for key, payload in self.payloads.items()
        }


async def run_primary_only(agent):
    token = set_provider_fallback_allowed(False)
    try:
        return await agent.run(
            questions=[question()],
            answer_key=[{"question_id": "q_1", "correct_answer": "C"}],
            curriculum=[
                {
                    "topic": "Hệ tuần hoàn",
                    "achievements": ["Mô tả được cấu tạo tim"],
                }
            ],
        )
    finally:
        reset_provider_fallback_allowed(token)


@pytest.mark.asyncio
async def test_primary_only_generation_uses_both_reviewers_once_and_records_consensus():
    agent = VerificationAgent()
    agent.dual_reviewers = FakeDualReviewers()

    result = await run_primary_only(agent)

    report = result["question_reports"][0]
    assert agent.dual_reviewers.calls == 1
    assert report["checks"]["dual_review"]["status"] == "consensus"
    assert set(report["checks"]["dual_review"]["reviewers"]) == {"deepseek", "gemini"}
    assert result["reviewer_summary"] == {
        "mode": "dual_mandatory",
        "reviewers": [
            {"label": "DeepSeek V4 Pro", "provider": "deepseek", "model": "deepseek-v4-pro"},
            {"label": "Gemini 3.7 Flash", "provider": "gemini", "model": "gemini-3.7-flash"},
        ],
        "consensus_questions": 1,
        "reviewed_questions": 1,
        "disagreement_questions": 0,
        "unavailable_questions": 0,
        "total_questions": 1,
    }


class FakeDeepSeekReviewer:
    mode = "deepseek_only"

    def __init__(self, payload=None, *, available=True):
        self.payload = payload or review_payload()
        self.is_available = available
        self.calls = 0

    def available(self):
        return self.is_available

    def required_reviewer_labels(self):
        return ["DeepSeek V4 Pro"]

    async def review(self, _prompt, *, response_model):
        assert response_model is IndependentVerificationOutput
        self.calls += 1
        return {"deepseek": reviewer_result("deepseek", self.payload)}


@pytest.mark.asyncio
async def test_deepseek_only_mode_records_one_review_without_claiming_consensus():
    agent = VerificationAgent()
    agent.dual_reviewers = FakeDeepSeekReviewer()

    result = await run_primary_only(agent)

    report = result["question_reports"][0]
    assert agent.dual_reviewers.calls == 1
    assert report["checks"]["dual_review"]["status"] == "reviewed"
    assert report["checks"]["dual_review"]["mode"] == "deepseek_only"
    assert set(report["checks"]["dual_review"]["reviewers"]) == {"deepseek"}
    assert report["checks"]["solve_compare"]["status"] == "match"
    assert result["reviewer_summary"] == {
        "mode": "deepseek_only",
        "reviewers": [
            {"label": "DeepSeek V4 Pro", "provider": "deepseek", "model": "deepseek-v4-pro"},
        ],
        "consensus_questions": 0,
        "reviewed_questions": 1,
        "disagreement_questions": 0,
        "unavailable_questions": 0,
        "total_questions": 1,
    }


@pytest.mark.asyncio
async def test_deepseek_only_mode_fails_closed_when_deepseek_is_unavailable():
    agent = VerificationAgent()
    agent.dual_reviewers = FakeDeepSeekReviewer(available=False)

    result = await run_primary_only(agent)

    report = result["question_reports"][0]
    assert agent.dual_reviewers.calls == 0
    assert report["checks"]["dual_review"]["required_reviewers"] == ["DeepSeek V4 Pro"]
    assert VerificationAgent.hard_failure_reasons(
        result, require_independent=True
    ) == {"q_1": ["semantic_review_unavailable"]}


@pytest.mark.asyncio
async def test_material_reviewer_disagreement_is_a_hard_failure():
    agent = VerificationAgent()
    gemini = review_payload(answer="A", answer_correct=False)
    agent.dual_reviewers = FakeDualReviewers(gemini=gemini)

    result = await run_primary_only(agent)

    report = result["question_reports"][0]
    assert report["checks"]["dual_review"]["status"] == "disagreement"
    assert "reviewer_disagreement" in VerificationAgent.hard_failure_reasons(result)["q_1"]


@pytest.mark.asyncio
async def test_difficulty_only_disagreement_is_visible_but_not_a_hard_failure():
    agent = VerificationAgent()
    gemini = review_payload(assessed_difficulty="thong_hieu")
    agent.dual_reviewers = FakeDualReviewers(gemini=gemini)

    result = await run_primary_only(agent)

    report = result["question_reports"][0]
    assert report["checks"]["dual_review"]["material_disagreement"] is False
    assert report["checks"]["dual_review"]["difficulty_agreement"] is False
    assert VerificationAgent.hard_failure_reasons(result) == {}
    assert any(issue["type"] == "difficulty_mismatch" for issue in report["issues"])


@pytest.mark.asyncio
async def test_missing_mandatory_reviewer_fails_closed_without_single_model_fallback():
    agent = VerificationAgent()
    agent.dual_reviewers = FakeDualReviewers(available=False)

    result = await run_primary_only(agent)

    report = result["question_reports"][0]
    assert agent.dual_reviewers.calls == 0
    assert report["checks"]["dual_review"]["status"] == "unavailable"
    assert VerificationAgent.hard_failure_reasons(
        result, require_independent=True
    ) == {"q_1": ["semantic_review_unavailable"]}


class FakeReviewerService:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def available(self):
        return True

    def generate_verification_json(self, _prompt, *, response_model):
        self.calls += 1
        return response_model.model_validate(deepcopy(self.payload)).model_dump(mode="json")


@pytest.mark.asyncio
async def test_dual_service_calls_each_peer_exactly_once():
    deepseek = FakeReviewerService(review_payload())
    gemini = FakeReviewerService(review_payload())
    service = DualVerificationService(reviewers=[
        Reviewer("deepseek", "DeepSeek V4 Pro", "deepseek", "deepseek-v4-pro", deepseek),
        Reviewer("gemini", "Gemini 3.7 Flash", "gemini", "gemini-3.7-flash", gemini),
    ])

    results = await service.review("review", response_model=IndependentVerificationOutput)

    assert set(results) == {"deepseek", "gemini"}
    assert deepseek.calls == gemini.calls == 1


@pytest.mark.asyncio
async def test_deepseek_only_service_never_constructs_or_calls_a_gemini_peer():
    deepseek = FakeReviewerService(review_payload())
    service = DualVerificationService(
        reviewers=[
            Reviewer("deepseek", "DeepSeek V4 Pro", "deepseek", "deepseek-v4-pro", deepseek),
        ],
        mode="deepseek_only",
    )

    results = await service.review("review", response_model=IndependentVerificationOutput)

    assert set(results) == {"deepseek"}
    assert service.required_reviewer_labels() == ["DeepSeek V4 Pro"]
    assert deepseek.calls == 1


def test_deepseek_only_default_reviewer_set_excludes_gemini():
    service = DualVerificationService(mode="deepseek_only")

    assert [reviewer.provider for reviewer in service.reviewers] == ["deepseek"]


@pytest.mark.asyncio
async def test_missing_reviewer_aborts_before_spending_generation_retry(monkeypatch):
    monkeypatch.setattr(settings, "AI_INTERACTIVE_REVIEW_MODE", "deepseek_only")
    service = ExamService.__new__(ExamService)
    service.verification_agent = MagicMock()
    service.verification_agent.hard_failure_reasons.return_value = {
        "q_1": ["semantic_review_unavailable"]
    }
    service.question_agent = SimpleNamespace(has_ai=True, run=AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        await service._repair_hard_failures(
            generated={"questions": [], "answer_key": [], "rubric": []},
            verification={"question_reports": []},
            specification=[],
            grade=8,
            curriculum=[],
        )

    assert exc_info.value.status_code == 503
    assert "DeepSeek V4 Pro" in exc_info.value.detail["message"]
    assert "Gemini" not in exc_info.value.detail["message"]
    service.question_agent.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_timeout_is_reported_as_reviewer_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "AI_INTERACTIVE_REVIEW_MODE", "deepseek_only")
    service = ExamService.__new__(ExamService)
    service.verification_agent = MagicMock()
    service.verification_agent.hard_failure_reasons.side_effect = [
        {"q_1": ["answer_incorrect"]},
        {"q_1": ["semantic_review_unavailable"]},
    ]
    service.question_agent = SimpleNamespace(
        has_ai=True,
        run=AsyncMock(
            return_value={
                "questions": [{"id": "q_1"}],
                "answer_key": [{"question_id": "q_1"}],
                "rubric": [{"question_id": "q_1"}],
            }
        ),
    )
    service.verification_agent.run = AsyncMock(return_value={"question_reports": []})

    with pytest.raises(HTTPException) as exc_info:
        await service._repair_hard_failures(
            generated={
                "questions": [{"id": "q_1"}],
                "answer_key": [{"question_id": "q_1"}],
                "rubric": [{"question_id": "q_1"}],
            },
            verification={"question_reports": []},
            specification=[{"question_id": "q_1"}],
            grade=8,
            curriculum=[],
        )

    assert exc_info.value.status_code == 503
    assert "DeepSeek V4 Pro" in exc_info.value.detail["message"]
    assert "Gemini" not in exc_info.value.detail["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['dual', 'deepseek_only'])
async def test_true_false_multiple_true_statements_are_not_competing_mcq_answers(mode):
    agent = VerificationAgent()
    q = {**question(), 'type': 'true_false', 'options': None, 'statements': [
        {'id': f's{i}', 'content': f'Phát biểu khoa học số {i}.', 'is_true': value}
        for i, value in enumerate([True, True, False, False], 1)
    ]}
    statements = [{'statement_id': s['id'], 'is_true': s['is_true']} for s in q['statements']]
    payload = review_payload()
    payload['solve'].update(your_answer='Hai ý đầu đúng', statement_answers=statements, multiple_correct=True)
    payload['quality']['single_correct_answer'] = False
    agent.dual_reviewers = FakeDualReviewers(payload, deepcopy(payload)) if mode == 'dual' else FakeDeepSeekReviewer(payload)
    token = set_provider_fallback_allowed(False)
    try:
        result = await agent.run(questions=[q], answer_key=[{'question_id': q['id'], 'answers': statements}])
    finally:
        reset_provider_fallback_allowed(token)
    report = result['question_reports'][0]
    assert report['checks']['solve_compare']['status'] == 'match'
    assert report['checks']['solve_compare']['multiple_correct'] is False
    assert not VerificationAgent.hard_failure_reasons(result, require_independent=True)


@pytest.mark.parametrize('defect', ['wrong', 'missing', 'duplicate', 'unknown', 'non_boolean'])
def test_true_false_still_rejects_wrong_or_incomplete_independent_answers(defect):
    agent = VerificationAgent()
    q = {'type': 'true_false', 'statements': [{'id': f's{i}'} for i in range(4)]}
    expected = [{'statement_id': f's{i}', 'is_true': i < 2} for i in range(4)]
    actual = deepcopy(expected)
    if defect == 'wrong': actual[0]['is_true'] = False
    if defect == 'missing': actual.pop()
    if defect == 'duplicate': actual.append(deepcopy(actual[0]))
    if defect == 'unknown': actual[0]['statement_id'] = 'other'
    if defect == 'non_boolean': actual[0]['is_true'] = 1
    result = agent._normalize_solve(q, {'answers': expected}, {'statement_answers': actual, 'multiple_correct': True})
    assert result['status'] == 'mismatch'


def test_mcq_multiple_correct_remains_a_hard_failure():
    agent = VerificationAgent()
    payload = review_payload()
    payload['solve']['multiple_correct'] = True
    payload['quality']['single_correct_answer'] = False
    report = agent._base_report(question())
    agent._apply_reviewer_consensus(report, question(), {'correct_answer': 'C'}, {'deepseek': reviewer_result('deepseek', payload)})
    agent._finalize_report(report)
    failures = agent.hard_failure_reasons({'question_reports': [report]})['q_1']
    assert 'independent_answer_mismatch' in failures
    assert 'multiple_correct_answers' in failures


def test_review_payload_separates_student_question_scientific_answer_and_scope():
    agent = VerificationAgent()
    q = {**question(), 'type': 'true_false', 'statements': [
        {'id': 's1', 'content': 'Nhiệt lượng đo bằng J.', 'is_true': True},
    ]}
    original = deepcopy(q)
    student = agent._question_payload(q)
    assert student['type'] == 'true_false'
    assert student['statements'] == [{'id': 's1', 'content': 'Nhiệt lượng đo bằng J.'}]
    assert q == original
    answer = {'explanation': 'Nhiệt lượng là năng lượng truyền.', 'citations': [{'excerpt': 'Nêu được...'}], 'source': {'secret': 'scope'}}
    assert agent._answer_payload(answer) == {'explanation': 'Nhiệt lượng là năng lượng truyền.'}
    prompt = agent._combined_review_prompt(q, answer)
    assert '"citations"' not in prompt and '"secret"' not in prompt
    assert 'THAY CHO tri thức khoa học' in prompt


def test_repair_feedback_includes_actionable_diagnosis_without_other_questions():
    feedback = ExamService._repair_feedback({'question_reports': [
        {'question_id': 'q_7', 'issues': [{'description': 'Chỉ hỏi định nghĩa.', 'suggestion': 'Dùng tình huống pha dung dịch.'}]},
        {'question_id': 'q_8', 'issues': [{'description': 'Unrelated'}]},
    ]}, {'q_7': ['ai_quality_issue']})
    assert set(feedback) == {'q_7'}
    assert 'Dùng tình huống pha dung dịch.' in feedback['q_7'][1]
