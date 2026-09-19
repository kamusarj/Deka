import pytest
from unittest.mock import AsyncMock
from app.agents.verification_agent import VerificationAgent
from app.schemas.ai_outputs import QualityVerificationOutput, SolveVerificationOutput


def mcq_question():
    return {
        "id": "q_1",
        "number": 1,
        "type": "multiple_choice",
        "difficulty": "nhan_biet",
        "content": "Tim người có bao nhiêu ngăn?",
        "options": {"A": "2", "B": "3", "C": "4", "D": "5"},
        "metadata": {"topic": "Hệ tuần hoàn", "achievement": "Mô tả được cấu tạo tim"},
    }


def test_short_answer_matches_equivalent_vietnamese_number_forms():
    agent = VerificationAgent()
    question = {"type": "short_answer"}
    answer = {"correct_answer": "bốn", "accept_variations": True}

    assert agent._answers_match(question, answer, "bốn", {"your_answer": "4"})
    assert not agent._answers_match(question, answer, "bốn", {"your_answer": "5"})


def test_essay_answer_matches_key_point_coverage_not_verbatim_prose():
    agent = VerificationAgent()
    question = {"type": "essay"}
    answer = {
        "model_answer": "Hệ hô hấp đưa oxygen vào máu và thải carbon dioxide.",
        "key_points": [
            "chức năng hệ hô hấp",
            "cung cấp oxygen",
            "loại bỏ carbon dioxide",
            "ý nghĩa trao đổi khí",
            "duy trì hoạt động sống",
        ],
    }
    solved = {
        "your_answer": (
            "Hệ hô hấp thực hiện trao đổi khí, đưa oxygen vào cơ thể, loại bỏ "
            "carbon dioxide và nhờ đó duy trì hoạt động sống."
        )
    }

    assert agent._answers_match(
        question,
        answer,
        answer["model_answer"],
        solved,
    )


def test_essay_answer_uses_full_independent_reasoning_when_conclusion_is_short():
    agent = VerificationAgent()
    question = {"type": "essay"}
    answer = {
        "model_answer": (
            "Quang hợp hấp thụ carbon dioxide và giải phóng oxygen; hô hấp "
            "sử dụng oxygen và giải phóng carbon dioxide."
        ),
        "key_points": [
            "Quang hợp hấp thụ carbon dioxide và giải phóng oxygen",
            "Hô hấp sử dụng oxygen và giải phóng carbon dioxide",
            "Hai quá trình bổ sung và tạo vòng tuần hoàn trong tự nhiên",
        ],
    }
    solved = {
        "your_answer": "Hai quá trình bổ sung nhau",
        "reasoning": (
            "Quang hợp hấp thụ carbon dioxide và giải phóng oxygen. Hô hấp "
            "sử dụng oxygen, đồng thời giải phóng carbon dioxide. Vì sản phẩm "
            "của quá trình này là nguyên liệu của quá trình kia, hai quá trình "
            "tạo vòng tuần hoàn vật chất trong tự nhiên."
        ),
    }

    assert agent._answers_match(
        question,
        answer,
        answer["model_answer"],
        solved,
    )


def test_essay_answer_rejects_unrelated_prose():
    agent = VerificationAgent()
    question = {"type": "essay"}
    answer = {
        "model_answer": "Hệ hô hấp đưa oxygen vào máu.",
        "key_points": ["chức năng hệ hô hấp", "cung cấp oxygen", "loại bỏ carbon dioxide"],
    }

    assert not agent._answers_match(
        question,
        answer,
        answer["model_answer"],
        {"your_answer": "Tim co bóp để đưa máu đi khắp cơ thể."},
    )


@pytest.mark.asyncio
async def test_verification_is_usable_without_ai():
    agent = VerificationAgent()
    agent.has_ai = False
    result = await agent.run(
        questions=[mcq_question()],
        answer_key=[{"question_id": "q_1", "correct_answer": "C"}],
        curriculum=[{"topic": "Hệ tuần hoàn", "achievements": ["Mô tả được cấu tạo tim"]}],
    )

    report = result["question_reports"][0]
    assert result["overall_status"] == "not_verified"
    assert report["status"] == "not_verified"
    assert report["verification_score"] is None
    assert report["checks"]["grounding"]["grounded"] is True
    assert report["checks"]["solve_compare"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_empty_verification_is_not_verified_instead_of_crashing():
    result = await VerificationAgent().run(
        questions=[],
        answer_key=[],
        curriculum=[],
    )

    assert result["overall_score"] is None
    assert result["overall_status"] == "not_verified"
    assert result["summary"]["total_questions"] == 0


@pytest.mark.asyncio
async def test_ambiguous_true_false_statement_needs_teacher_review():
    agent = VerificationAgent()
    agent.has_ai = False
    question = {
        "id": "q_2",
        "number": 2,
        "type": "true_false",
        "difficulty": "thong_hieu",
        "content": "Chọn đúng sai.",
        "statements": [
            {"id": "s_2_1", "content": "Sinh vật thường có tế bào.", "is_true": True},
            {"id": "s_2_2", "content": "Không phải tất cả đều không có tế bào.", "is_true": True},
        ],
        "metadata": {"topic": "Tế bào", "achievement": "Nêu được khái niệm tế bào"},
    }
    result = await agent.run(
        questions=[question],
        answer_key=[{"question_id": "q_2", "answers": []}],
        curriculum=[{"topic": "Tế bào", "achievements": ["Nêu được khái niệm tế bào"]}],
    )

    report = result["question_reports"][0]
    assert report["status"] == "needs_review"
    assert {issue["type"] for issue in report["issues"]} >= {"ambiguous_statement", "double_negative"}


@pytest.mark.asyncio
async def test_grounding_skips_missing_question_scope_owned_by_validator():
    agent = VerificationAgent()
    agent.has_ai = False
    question = mcq_question()
    question["metadata"]["achievement"] = None

    result = await agent.run(
        questions=[question],
        answer_key=[{"question_id": "q_1", "correct_answer": "C"}],
        curriculum=[
            {"topic": "Hệ tuần hoàn", "achievements": ["Mô tả được cấu tạo tim"]}
        ],
    )

    report = result["question_reports"][0]
    assert report["checks"]["grounding"]["status"] == "skipped"
    assert report["checks"]["grounding"]["reason"] == "Question scope metadata incomplete"
    assert not any(
        issue["type"] == "curriculum_grounding" for issue in report["issues"]
    )


@pytest.mark.asyncio
async def test_grounding_warns_when_complete_metadata_lacks_objective_evidence():
    agent = VerificationAgent()
    agent.has_ai = False

    result = await agent.run(
        questions=[mcq_question()],
        answer_key=[{"question_id": "q_1", "correct_answer": "C"}],
        curriculum=[{"topic": "Hệ tuần hoàn", "achievements": [None, ""]}],
    )

    report = result["question_reports"][0]
    assert report["checks"]["grounding"]["grounded"] is False
    assert report["checks"]["grounding"]["status"] == "needs_review"
    assert any(issue["type"] == "curriculum_grounding" for issue in report["issues"])


@pytest.mark.asyncio
async def test_ai_answer_mismatch_is_flagged_but_never_rejected():
    agent = VerificationAgent()
    agent.has_ai = True
    responses = iter([
        {"your_answer": "A", "multiple_correct": False, "confidence": 0.9, "reasoning": "..."},
        {"is_valid": True, "issues_found": [], "difficulty_matches": True},
    ])
    response_models = []

    def fake_verification(_prompt, **kwargs):
        response_models.append(kwargs.get("response_model"))
        return next(responses)

    agent.llm.generate_verification_json = fake_verification

    result = await agent.run(
        questions=[mcq_question()],
        answer_key=[{"question_id": "q_1", "correct_answer": "C"}],
        curriculum=[{"topic": "Hệ tuần hoàn", "achievements": ["Mô tả được cấu tạo tim"]}],
    )

    report = result["question_reports"][0]
    assert report["status"] == "needs_review"
    assert result["summary"]["auto_rejected"] == 0
    assert any(issue["type"] == "answer_mismatch" for issue in report["issues"])
    assert response_models == [SolveVerificationOutput, QualityVerificationOutput]


@pytest.mark.asyncio
async def test_provider_failure_opens_circuit_for_remaining_questions():
    agent = VerificationAgent()
    agent.has_ai = True
    agent._run_ai_check = AsyncMock(side_effect=RuntimeError("rate limited"))
    questions = [
        {**mcq_question(), "id": f"q_{index}", "number": index}
        for index in range(1, 4)
    ]

    result = await agent.run(
        questions=questions,
        answer_key=[
            {"question_id": question["id"], "correct_answer": "C"}
            for question in questions
        ],
        curriculum=[
            {"topic": "Hệ tuần hoàn", "achievements": ["Mô tả được cấu tạo tim"]}
        ],
    )

    assert agent._run_ai_check.await_count == 1
    assert result["summary"]["not_verified"] == 3
    assert "earlier provider failure" in result["question_reports"][1]["checks"]["solve_compare"]["reason"]


@pytest.mark.asyncio
async def test_streaming_verification_uses_the_same_provider_circuit():
    agent = VerificationAgent()
    agent.has_ai = True
    agent._run_ai_check = AsyncMock(side_effect=TimeoutError("provider timeout"))
    questions = [
        {**mcq_question(), "id": f"q_{index}", "number": index}
        for index in range(1, 3)
    ]

    events = [
        event
        async for event in agent.run_with_progress(
            questions=questions,
            answer_key=[
                {"question_id": question["id"], "correct_answer": "C"}
                for question in questions
            ],
            curriculum=[
                {"topic": "Hệ tuần hoàn", "achievements": ["Mô tả được cấu tạo tim"]}
            ],
        )
    ]

    assert agent._run_ai_check.await_count == 1
    assert events[-1][1]["summary"]["not_verified"] == 2
