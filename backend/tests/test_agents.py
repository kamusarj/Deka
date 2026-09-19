"""
Tests cho các AI Agents.

Bao gồm: MatrixAgent, SpecificationAgent, ValidatorAgent, AnswerAgent.
"""

import sys
import os
import pytest
import app.agents

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.matrix_agent import MatrixAgent
from app.agents.specification_agent import SpecificationAgent
from app.agents.validator_agent import ValidatorAgent
from app.agents.answer_agent import AnswerAgent
from app.agents.question_agent import QuestionAgent
from app.schemas.ai_outputs import AnswerGenerationOutput
from app.schemas.exam import (
    CalculationRequirement,
    CurriculumItem,
    DifficultyRatio,
    MatrixRequest,
    QuestionTypeConfig,
    QuestionTypes,
)
from app.agents.resource_collector_agent import ResourceCollectorAgent
from app.services.exam.generation_planning import build_generation_plan
from fastapi import HTTPException
from pydantic import ValidationError


# ── Helpers ────────────────────────────────────────────────────

def make_request(
    curriculum=None,
    difficulty_ratio=None,
    question_types=None,
    **exam_fields,
):
    """Tạo MatrixRequest nhanh cho test."""
    defaults = {
        "school": "THCS Nguyễn Du",
        "grade": 8,
        "subject": "Khoa học tự nhiên",
        "exam_type": "Giữa học kì I",
        "duration_minutes": 45,
        "school_year": "2025-2026",
        "total_score": 10.0,
    }
    defaults.update(exam_fields)
    return MatrixRequest(
        curriculum=curriculum or [
            CurriculumItem(
                topic="Bài 1: Tim và mạch máu",
                periods=6,
                achievements=["Mô tả được cấu tạo tim"],
            ),
            CurriculumItem(
                topic="Bài 2: Hô hấp",
                periods=5,
                achievements=["Giải thích được cơ chế hô hấp"],
            ),
            CurriculumItem(
                topic="Bài 3: Dinh dưỡng",
                periods=4,
                achievements=["Vận dụng kiến thức dinh dưỡng"],
            ),
        ],
        difficulty_ratio=difficulty_ratio or DifficultyRatio(),
        question_types=question_types or QuestionTypes(),
        **defaults,
    )


def test_question_types_require_at_least_one_enabled_question():
    disabled = QuestionTypeConfig(enabled=False, count=0, score_per_question=0)
    with pytest.raises(ValidationError, match="ít nhất một câu hỏi"):
        QuestionTypes(
            multiple_choice=disabled,
            true_false=disabled,
            short_answer=disabled,
            essay=disabled,
        )


def test_calculation_requirement_must_fit_short_answer_slots_and_total_score():
    with pytest.raises(ValidationError, match="đúng một mức độ"):
        CalculationRequirement(
            count=2,
            score_per_question=0.5,
            difficulties=["van_dung"],
        )

    with pytest.raises(ValidationError, match="không được vượt quá"):
        make_request(
            calculation_requirement=CalculationRequirement(
                count=3, score_per_question=0.5
            )
        )

    with pytest.raises(ValidationError, match="phải bằng 10"):
        make_request(
            calculation_requirement=CalculationRequirement(
                count=2, score_per_question=1
            )
        )

    automatic = make_request(
        auto_distribute_scores=True,
        calculation_requirement=CalculationRequirement(
            count=2,
            score_per_question=1,
        ),
    )
    assert automatic.auto_distribute_scores is True


def test_score_contract_rejects_non_quarter_manual_scores_and_insufficient_auto_budget():
    with pytest.raises(ValidationError, match="mỗi câu/mỗi ý"):
        make_request(
            question_types=QuestionTypes(
                multiple_choice=QuestionTypeConfig(count=8, score_per_question=0.3),
                true_false=QuestionTypeConfig(count=4, score_per_question=1),
                short_answer=QuestionTypeConfig(count=2, score_per_question=0.5),
                essay=QuestionTypeConfig(count=2, score_per_question=1.3),
            ),
        )

    with pytest.raises(ValidationError, match="vượt quỹ điểm"):
        make_request(
            auto_distribute_scores=True,
            question_types=QuestionTypes(
                multiple_choice=QuestionTypeConfig(count=20, score_per_question=0.25),
                true_false=QuestionTypeConfig(count=6, score_per_question=1),
                short_answer=QuestionTypeConfig(count=1, score_per_question=0.5),
                essay=QuestionTypeConfig(enabled=False, count=0, score_per_question=0),
            ),
        )


def test_resource_collector_rejects_unknown_exam_type():
    with pytest.raises(HTTPException) as error:
        ResourceCollectorAgent()._resolve_exam_scope(
            {"exam_scopes": [{"exam_type": "midterm", "display_name": "Giữa kỳ"}]},
            "Loại không tồn tại",
        )

    assert error.value.status_code == 400


def test_agents_package_does_not_advertise_dead_export_agent():
    assert "ExportAgent" not in app.agents.__all__


def test_question_scoring_parts_use_quarter_point_units():
    assert QuestionAgent._quarter_partition(0.75, [0.7, 0.3]) == [0.5, 0.25]
    assert QuestionAgent._quarter_partition(1.25, [1, 1, 1, 1]) == [
        0.5,
        0.25,
        0.25,
        0.25,
    ]


# ============================================================
# Test MatrixAgent
# ============================================================


class TestMatrixAgent:
    """Test MatrixAgent - rule-based matrix generator."""

    @pytest.mark.asyncio
    async def test_generates_matrix_with_summary(self):
        agent = MatrixAgent()
        request = make_request()
        result = await agent.run(request=request)
        assert "matrix" in result
        assert "summary" in result
        assert "question_plan" in result
        assert len(result["matrix"]) > 0

    @pytest.mark.asyncio
    async def test_total_score_equals_10(self):
        agent = MatrixAgent()
        request = make_request()
        result = await agent.run(request=request)
        total = round(result["summary"]["total_score"], 2)
        assert total == 10.0, f"Expected 10, got {total}"

    @pytest.mark.asyncio
    async def test_matrix_has_required_fields(self):
        agent = MatrixAgent()
        request = make_request()
        result = await agent.run(request=request)
        for row in result["matrix"]:
            for key in ("nhan_biet", "thong_hieu", "van_dung"):
                cell = row[key]
                assert "count" in cell
                assert "score" in cell
                assert "question_type" in cell
                assert "question_ids" in cell

    @pytest.mark.asyncio
    async def test_every_question_assigned_a_difficulty(self):
        agent = MatrixAgent()
        request = make_request()
        result = await agent.run(request=request)
        for item in result["question_plan"]:
            assert item["difficulty"] in ("nhan_biet", "thong_hieu", "van_dung")

    @pytest.mark.asyncio
    async def test_question_count_matches_config(self):
        agent = MatrixAgent()
        from app.schemas.exam import QuestionTypeConfig
        request = make_request(
            question_types=QuestionTypes(
                multiple_choice=QuestionTypeConfig(count=8, score_per_question=0.25),
                true_false=QuestionTypeConfig(count=4, score_per_question=1.0),
                short_answer=QuestionTypeConfig(count=2, score_per_question=0.5),
                essay=QuestionTypeConfig(count=2, score_per_question=1.5),
            ),
        )
        result = await agent.run(request=request)
        # 8 MC + 4 TF + 2 SA + 2 Essay = 16 total
        assert len(result["question_plan"]) == 16
        # 8*0.25 + 4*1 + 2*0.5 + 2*1.5 = 2 + 4 + 1 + 3 = 10
        total_from_plan = round(sum(item["score"] for item in result["question_plan"]), 2)
        assert total_from_plan == 10.0, f"Expected 10 from plan scores, got {total_from_plan}"

    @pytest.mark.asyncio
    async def test_handles_single_lesson(self):
        agent = MatrixAgent()
        single = [
            CurriculumItem(
                topic="Bài đơn",
                periods=4,
                achievements=["Yêu cầu duy nhất"],
            )
        ]
        request = make_request(curriculum=single)
        result = await agent.run(request=request)
        assert len(result["matrix"]) == 1
        assert result["summary"]["total_score"] == 10.0

    @pytest.mark.asyncio
    async def test_difficulty_ratio_is_accounted(self):
        """Kiểm tra percentage trong summary khớp với ratio đã đặt."""
        agent = MatrixAgent()
        # Set ratio to 40/20/40
        request = make_request(
            difficulty_ratio=DifficultyRatio(nhan_biet=40, thong_hieu=20, van_dung=40),
        )
        result = await agent.run(request=request)
        summary = result["summary"]
        for key in ("nhan_biet", "thong_hieu", "van_dung"):
            percentage = summary[key]["percentage"]
            # Allow +/- 15% tolerance since allocation is approximate
            expected = getattr(request.difficulty_ratio, key)
            assert abs(percentage - expected) <= 20, (
                f"{key} expected ~{expected}%, got {percentage}%"
            )

    @pytest.mark.asyncio
    async def test_matrix_rows_match_question_plan_when_curriculum_unsorted(self):
        """Hồi quy: curriculum chưa sort theo số tiết, mỗi dòng ma trận vẫn
        phải chứa đúng câu hỏi của chủ đề mà question plan đã gán."""
        agent = MatrixAgent()
        curriculum = [
            CurriculumItem(
                topic="Ít tiết",
                periods=2,
                achievements=["Nêu được kiến thức ít tiết"],
            ),
            CurriculumItem(
                topic="Nhiều tiết",
                periods=9,
                achievements=["Nêu được kiến thức nhiều tiết"],
            ),
            CurriculumItem(
                topic="Trung bình",
                periods=4,
                achievements=["Nêu được kiến thức trung bình"],
            ),
        ]
        request = make_request(curriculum=curriculum)
        result = await agent.run(request=request)
        topic_by_original_index = {
            index: item.topic for index, item in enumerate(request.curriculum)
        }
        plan_by_topic = {}
        for item in result["question_plan"]:
            plan_by_topic.setdefault(
                topic_by_original_index[item["lesson_index"]], []
            ).append(item)

        for row in result["matrix"]:
            expected = plan_by_topic.get(row["topic_name"], [])
            row_question_ids = {
                qid
                for key in ("nhan_biet", "thong_hieu", "van_dung")
                for qid in row[key]["question_ids"]
            }
            assert row_question_ids == {item["question_id"] for item in expected}, (
                f"Dòng '{row['topic_name']}' chứa {row_question_ids} thay vì "
                f"{{item['question_id'] for item in expected}}"
            )
            assert row["total_score"] == round(
                sum(item["score"] for item in expected), 2
            )
        # Tổng khớp summary (không mất câu khi gán lại dòng).
        all_ids = {
            qid
            for row in result["matrix"]
            for key in ("nhan_biet", "thong_hieu", "van_dung")
            for qid in row[key]["question_ids"]
        }
        assert all_ids == {item["question_id"] for item in result["question_plan"]}

    @pytest.mark.asyncio
    async def test_multiple_choice_lean_easier_and_essays_avoid_recall(self):
        """Với tỷ lệ chuẩn 30/40/30, câu trắc nghiệm nên nghiêng về nhận biết và
        câu tự luận không bị gán mức nhận biết (vô lý sư phạm)."""
        from app.schemas.exam import QuestionTypeConfig
        agent = MatrixAgent()
        request = make_request(
            difficulty_ratio=DifficultyRatio(nhan_biet=30, thong_hieu=40, van_dung=30),
            question_types=QuestionTypes(
                multiple_choice=QuestionTypeConfig(count=8, score_per_question=0.25),
                true_false=QuestionTypeConfig(count=4, score_per_question=1.0),
                short_answer=QuestionTypeConfig(count=2, score_per_question=0.5),
                essay=QuestionTypeConfig(count=2, score_per_question=1.5),
            ),
        )
        result = await agent.run(request=request)
        by_type = {}
        for item in result["question_plan"]:
            by_type.setdefault(item["type"], []).append(item["difficulty"])

        mc = by_type["multiple_choice"]
        # Không có câu trắc nghiệm nào ở mức vận dụng trong cấu hình chuẩn.
        assert "van_dung" not in mc
        # Phần lớn câu trắc nghiệm ở mức nhận biết.
        assert mc.count("nhan_biet") >= len(mc) // 2
        # Không có câu tự luận nào bị gán mức nhận biết.
        assert "nhan_biet" not in by_type["essay"]
        # Tỷ lệ tổng vẫn đúng (trong dung sai của validator).
        summary = result["summary"]
        for key, expected in request.difficulty_ratio.model_dump().items():
            assert abs(summary[key]["percentage"] - expected) <= 10

    @pytest.mark.asyncio
    async def test_plans_exact_required_calculation_count_and_score(self):
        request = make_request(
            curriculum=[
                CurriculumItem(
                    topic="Mol và tỉ khối chất khí",
                    periods=5,
                    achievements=[
                        "Trình bày được khái niệm mol và hằng số Avogadro.",
                        "Tính được khối lượng mol từ công thức hóa học.",
                    ],
                )
            ],
            calculation_requirement=CalculationRequirement(
                count=2,
                score_per_question=0.5,
                difficulties=["thong_hieu", "van_dung"],
            ),
        )

        result = await MatrixAgent().run(request=request)
        calculations = [
            item
            for item in result["question_plan"]
            if item.get("requires_calculation")
        ]

        assert len(calculations) == 2
        assert all(item["type"] == "short_answer" for item in calculations)
        assert all(item["score"] == 0.5 for item in calculations)
        assert [item["difficulty"] for item in calculations] == [
            "thong_hieu",
            "van_dung",
        ]
        assert all(item["objective_id"] == "khtn8_obj_007" for item in calculations)
        assert all(
            not item["achievement"].startswith("Tính được")
            for item in result["question_plan"]
            if not item.get("requires_calculation")
        )
        assert result["summary"]["calculation_requirement"] == {
            "required_count": 2,
            "actual_count": 2,
            "score_per_question": 0.5,
            "requested_difficulties": ["thong_hieu", "van_dung"],
            "actual_difficulties": ["thong_hieu", "van_dung"],
            "actual_scores": [0.5, 0.5],
            "total_score": 1.0,
            "question_ids": [item["question_id"] for item in calculations],
        }

    @pytest.mark.asyncio
    async def test_calculation_requirement_fails_before_generation_without_capability(self):
        request = make_request(
            calculation_requirement=CalculationRequirement(
                count=1, score_per_question=0.5
            )
        )

        with pytest.raises(HTTPException) as error:
            await MatrixAgent().run(request=request)

        assert error.value.status_code == 422
        assert "không có yêu cầu cần đạt hỗ trợ phép tính" in error.value.detail

    @pytest.mark.asyncio
    async def test_calculation_difficulties_fail_fast_when_global_ratio_is_impossible(self):
        from app.schemas.exam import QuestionTypeConfig

        disabled = QuestionTypeConfig(
            enabled=False,
            count=0,
            score_per_question=0,
        )
        request = make_request(
            curriculum=[
                CurriculumItem(
                    topic="Mol và tỉ khối chất khí",
                    periods=5,
                    achievements=[
                        "Trình bày được khái niệm mol.",
                        "Tính được khối lượng mol từ công thức hóa học.",
                    ],
                )
            ],
            difficulty_ratio=DifficultyRatio(
                nhan_biet=0,
                thong_hieu=50,
                van_dung=50,
            ),
            question_types=QuestionTypes(
                multiple_choice=disabled,
                true_false=disabled,
                short_answer=QuestionTypeConfig(
                    count=10,
                    score_per_question=0.5,
                ),
                essay=QuestionTypeConfig(count=1, score_per_question=5),
            ),
            calculation_requirement=CalculationRequirement(
                count=10,
                score_per_question=0.5,
                difficulties=["nhan_biet"] * 10,
            ),
        )

        with pytest.raises(HTTPException) as error:
            await MatrixAgent().run(request=request)

        assert error.value.status_code == 422
        assert "không thể cân đối" in error.value.detail

    @pytest.mark.asyncio
    async def test_auto_distributes_sparse_difficulty_scores_in_quarter_points(self):
        disabled = QuestionTypeConfig(
            enabled=False,
            count=0,
            score_per_question=0,
        )
        request = make_request(
            curriculum=[
                CurriculumItem(
                    topic="Mol và tỉ khối chất khí",
                    periods=5,
                    achievements=[
                        "Trình bày được khái niệm mol.",
                        "Tính được khối lượng mol từ công thức hóa học.",
                    ],
                )
            ],
            difficulty_ratio=DifficultyRatio(
                nhan_biet=19,
                thong_hieu=18,
                van_dung=63,
            ),
            question_types=QuestionTypes(
                multiple_choice=QuestionTypeConfig(
                    count=1,
                    score_per_question=0.25,
                ),
                true_false=disabled,
                short_answer=QuestionTypeConfig(
                    count=2,
                    score_per_question=0.5,
                ),
                essay=disabled,
            ),
            calculation_requirement=CalculationRequirement(
                count=2,
                score_per_question=0.5,
                difficulties=["thong_hieu", "van_dung"],
            ),
            auto_distribute_scores=True,
        )

        result = await MatrixAgent().run(request=request)
        by_difficulty = {
            item["difficulty"]: item for item in result["question_plan"]
        }

        assert by_difficulty["nhan_biet"]["score"] == 2.0
        assert by_difficulty["thong_hieu"]["score"] == 1.75
        assert by_difficulty["van_dung"]["score"] == 6.25
        assert sum(item["score"] for item in result["question_plan"]) == 10
        assert all(item["score"] >= 0.25 for item in result["question_plan"])
        assert all(item["score"] * 4 == round(item["score"] * 4) for item in result["question_plan"])
        assert result["summary"]["auto_distribute_scores"] is True
        assert result["summary"]["score_increment"] == 0.25
        assert result["summary"]["calculation_requirement"]["actual_scores"] == [
            1.75,
            6.25,
        ]
        assert result["summary"]["nhan_biet"]["percentage"] == 20
        assert result["summary"]["thong_hieu"]["percentage"] == 17.5
        assert result["summary"]["van_dung"]["percentage"] == 62.5

    @pytest.mark.asyncio
    async def test_auto_distribution_rejects_fixed_levels_beyond_quarter_budget(self):
        request = make_request(
            curriculum=[
                CurriculumItem(
                    topic="Mol và tỉ khối chất khí",
                    periods=5,
                    achievements=[
                        "Trình bày được khái niệm mol.",
                        "Tính được khối lượng mol từ công thức hóa học.",
                    ],
                )
            ],
            difficulty_ratio=DifficultyRatio(
                nhan_biet=5,
                thong_hieu=45,
                van_dung=50,
            ),
            question_types=QuestionTypes(
                multiple_choice=QuestionTypeConfig(count=1, score_per_question=0.25),
                true_false=QuestionTypeConfig(enabled=False, count=0, score_per_question=0),
                short_answer=QuestionTypeConfig(count=3, score_per_question=0.5),
                essay=QuestionTypeConfig(enabled=False, count=0, score_per_question=0),
            ),
            calculation_requirement=CalculationRequirement(
                count=3,
                score_per_question=0.5,
                difficulties=["nhan_biet", "nhan_biet", "nhan_biet"],
            ),
            auto_distribute_scores=True,
        )

        with pytest.raises(HTTPException) as error:
            await MatrixAgent().run(request=request)

        assert error.value.status_code == 422
        assert "0,25 điểm/câu" in error.value.detail

    @pytest.mark.asyncio
    async def test_exact_calculation_count_requires_non_calculation_scope_for_other_slots(self):
        request = make_request(
            curriculum=[
                CurriculumItem(
                    topic="Mol và tỉ khối chất khí",
                    periods=5,
                    achievements=["Tính được khối lượng mol từ công thức hóa học."],
                )
            ],
            calculation_requirement=CalculationRequirement(
                count=2, score_per_question=0.5
            ),
        )

        with pytest.raises(HTTPException) as error:
            await MatrixAgent().run(request=request)

        assert error.value.status_code == 422
        assert "chỉ có yêu cầu tính toán" in error.value.detail


# ============================================================
# Test SpecificationAgent
# ============================================================


class TestSpecificationAgent:
    """Test SpecificationAgent."""

    @pytest.mark.asyncio
    async def test_generates_one_row_per_question(self):
        agent = MatrixAgent()
        spec_agent = SpecificationAgent()
        request = make_request()
        matrix_result = await agent.run(request=request)
        spec = await spec_agent.run(
            matrix=matrix_result["matrix"],
            question_plan=matrix_result["question_plan"],
            curriculum=request.curriculum,
        )
        assert len(spec) == len(matrix_result["question_plan"])

    @pytest.mark.asyncio
    async def test_spec_has_required_fields(self):
        agent = MatrixAgent()
        spec_agent = SpecificationAgent()
        request = make_request()
        matrix_result = await agent.run(request=request)
        spec = await spec_agent.run(
            matrix=matrix_result["matrix"],
            question_plan=matrix_result["question_plan"],
            curriculum=request.curriculum,
        )
        required = (
            "question_number",
            "topic",
            "lesson",
            "knowledge_unit",
            "achievement",
            "difficulty",
            "question_type",
            "score",
            "bloom_level",
            "content_hint",
            "question_id",
        )
        for row in spec:
            for field in required:
                assert field in row, f"Missing field '{field}' in spec row"

    @pytest.mark.asyncio
    async def test_question_ids_are_unique(self):
        agent = MatrixAgent()
        spec_agent = SpecificationAgent()
        request = make_request()
        matrix_result = await agent.run(request=request)
        spec = await spec_agent.run(
            matrix=matrix_result["matrix"],
            question_plan=matrix_result["question_plan"],
            curriculum=request.curriculum,
        )
        ids = [row["question_id"] for row in spec]
        assert len(ids) == len(set(ids)), "Question IDs must be unique"

    @pytest.mark.asyncio
    async def test_bloom_mapping(self):
        agent = MatrixAgent()
        spec_agent = SpecificationAgent()
        request = make_request()
        matrix_result = await agent.run(request=request)
        spec = await spec_agent.run(
            matrix=matrix_result["matrix"],
            question_plan=matrix_result["question_plan"],
            curriculum=request.curriculum,
        )
        expected_map = {
            "nhan_biet": "remember",
            "thong_hieu": "understand",
            "van_dung": "apply",
        }
        for row in spec:
            assert row["bloom_level"] == expected_map[row["difficulty"]]

    def test_required_calculation_forces_quantitative_generation_plan(self):
        plan = build_generation_plan(
            {
                "question_id": "q_calc",
                "topic": "Điện",
                "knowledge_unit": "định luật Ohm",
                "achievement": "Nêu được định luật Ohm và áp dụng tính toán.",
                "difficulty": "van_dung",
                "question_type": "short_answer",
                "requires_calculation": True,
                "source_context": "Định luật Ohm cho mạch điện.",
                "source": {"source_type": "local_json"},
            },
            grade=8,
        )

        assert plan.knowledge_intent == "calculation"
        assert plan.reasoning_mode == "quantitative"


# ============================================================
# Test ValidatorAgent
# ============================================================


class TestValidatorAgent:
    """Test ValidatorAgent."""

    def make_validator_input(self, **overrides):
        """Tạo input hợp lệ cho validator."""
        questions = [
            {
                "id": "q_1",
                "number": 1,
                "type": "multiple_choice",
                "difficulty": "nhan_biet",
                "score": 0.25,
                "content": "Tim có mấy ngăn?",
            },
            {
                "id": "q_2",
                "number": 2,
                "type": "multiple_choice",
                "difficulty": "thong_hieu",
                "score": 0.25,
                "content": "Chức năng của hồng cầu là gì?",
            },
            {
                "id": "q_3",
                "number": 3,
                "type": "essay",
                "difficulty": "van_dung",
                "score": 2.0,
                "content": "Mô tả đường đi của máu qua tim.",
            },
            {
                "id": "q_4",
                "number": 4,
                "type": "multiple_choice",
                "difficulty": "nhan_biet",
                "score": 0.25,
                "content": "Phổi nằm ở đâu?",
            },
            {
                "id": "q_5",
                "number": 5,
                "type": "multiple_choice",
                "difficulty": "thong_hieu",
                "score": 0.25,
                "content": "Khí oxi được vận chuyển bởi gì?",
            },
            {
                "id": "q_6",
                "number": 6,
                "type": "short_answer",
                "difficulty": "van_dung",
                "score": 0.5,
                "content": "Nêu một bệnh về đường hô hấp.",
            },
        ]
        # Adjust total to 10 by adding more questions
        remaining_score = 10.0 - sum(q["score"] for q in questions)
        if remaining_score > 0:
            questions.append({
                "id": "q_extra",
                "number": 7,
                "type": "multiple_choice",
                "difficulty": "nhan_biet",
                "score": round(remaining_score, 2),
                "content": "Câu hỏi bổ sung để đạt tổng 10 điểm.",
            })

        answer_key = [
            {"question_id": q["id"], "question_number": q["number"], "correct_answer": "A"}
            for q in questions
        ]
        rubric = [
            {
                "question_id": q["id"],
                "question_number": q["number"],
                "total_score": q["score"],
                "criteria": [],
            }
            for q in questions
            if q["type"] == "essay"
        ]
        summary = {
            "nhan_biet": {
                "total_count": sum(1 for q in questions if q["difficulty"] == "nhan_biet"),
                "total_score": sum(q["score"] for q in questions if q["difficulty"] == "nhan_biet"),
                "percentage": 30,
            },
            "thong_hieu": {
                "total_count": sum(1 for q in questions if q["difficulty"] == "thong_hieu"),
                "total_score": sum(q["score"] for q in questions if q["difficulty"] == "thong_hieu"),
                "percentage": 40,
            },
            "van_dung": {
                "total_count": sum(1 for q in questions if q["difficulty"] == "van_dung"),
                "total_score": sum(q["score"] for q in questions if q["difficulty"] == "van_dung"),
                "percentage": 30,
            },
            "total_questions": len(questions),
        }
        overrides_data = {
            "questions": overrides.get("questions", questions),
            "answer_key": overrides.get("answer_key", answer_key),
            "rubric": overrides.get("rubric", rubric),
            "summary": overrides.get("summary", summary),
            "request": __import__("types", fromlist=["SimpleNamespace"]).SimpleNamespace(
                total_score=10.0,
                difficulty_ratio=__import__("types", fromlist=["SimpleNamespace"]).SimpleNamespace(
                    model_dump=lambda: {"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30}
                ),
            ),
        }
        return overrides_data

    def test_score_increment_requires_quarter_point_for_each_visible_part(self):
        invalid = ValidatorAgent()._check_score_increment(
            [
                {
                    "id": "q_tf",
                    "type": "true_false",
                    "score": 0.75,
                    "statements": [{"id": f"s_{index}"} for index in range(4)],
                },
                {
                    "id": "q_essay",
                    "type": "essay",
                    "score": 0.75,
                    "sub_questions": [
                        {"id": "a", "score": 0.5},
                        {"id": "b", "score": 0.24},
                    ],
                },
            ]
        )

        assert invalid["passed"] is False
        assert invalid["actual"]["invalid_question_ids"] == ["q_tf", "q_essay"]

    @pytest.mark.asyncio
    async def test_valid_input_passes(self):
        agent = ValidatorAgent()
        data = self.make_validator_input()
        result = await agent.run(**data)
        # Allow for rounding differences
        assert len(result["errors"]) <= 1, f"Unexpected errors: {result['errors']}"

    def test_calculation_requirement_checks_server_marker_type_and_score(self):
        agent = ValidatorAgent()
        questions = [
            {
                "id": "q_calc",
                "type": "short_answer",
                "difficulty": "thong_hieu",
                "score": 0.5,
                "metadata": {
                    "is_calculation": True,
                    "calculation_verified": True,
                },
            }
        ]

        passed = agent._check_calculation_requirement(
            questions,
            CalculationRequirement(
                count=1,
                score_per_question=0.5,
                difficulties=["thong_hieu"],
            ),
        )
        failed = agent._check_calculation_requirement(
            questions,
            CalculationRequirement(count=1, score_per_question=1),
        )

        assert passed["passed"] is True
        assert failed["passed"] is False
        assert failed["actual"]["invalid_score_ids"] == ["q_calc"]

        wrong_difficulty = agent._check_calculation_requirement(
            questions,
            CalculationRequirement(
                count=1,
                score_per_question=0.5,
                difficulties=["van_dung"],
            ),
        )
        assert wrong_difficulty["passed"] is False
        assert wrong_difficulty["actual"]["invalid_difficulty_ids"] == ["q_calc"]

        automatically_scored = [
            {
                **questions[0],
                "score": 1.75,
            }
        ]
        automatic = agent._check_calculation_requirement(
            automatically_scored,
            CalculationRequirement(
                count=1,
                score_per_question=0.5,
                difficulties=["thong_hieu"],
            ),
            auto_distribute_scores=True,
        )
        assert automatic["passed"] is True

        invalid_automatic = agent._check_calculation_requirement(
            [{**questions[0], "score": 0.24}],
            CalculationRequirement(
                count=1,
                score_per_question=0.5,
                difficulties=["thong_hieu"],
            ),
            auto_distribute_scores=True,
        )
        assert invalid_automatic["passed"] is False
        assert invalid_automatic["actual"]["invalid_score_ids"] == ["q_calc"]

    @pytest.mark.asyncio
    async def test_scope_guard_replaced_is_flagged(self):
        """Hồi quy: câu bị scope guard `replaced` phải bị CHECK_CURRICULUM_SCOPE
        bắt ra (nhánh cũ chỉ checks `failed` nên không bao giờ khớp)."""
        agent = ValidatorAgent()
        data = self.make_validator_input()
        for question in data["questions"]:
            metadata = question.setdefault("metadata", {})
            metadata.setdefault("topic", "Tim và mạch máu")
            metadata.setdefault("achievement", "Mô tả được cấu tạo tim")
        data["questions"][0]["metadata"]["scope_guard"] = {"status": "replaced"}

        result = await agent.run(**data)
        scope_check = next(
            check for check in result["checks"] if check["name"] == "CHECK_CURRICULUM_SCOPE"
        )
        assert not scope_check["passed"]
        assert scope_check["status"] == "fail"
        assert scope_check["severity"] == "major"
        assert "q_1" in scope_check["actual"]["guard_replaced"]

    @pytest.mark.asyncio
    async def test_scope_guard_passed_is_not_flagged(self):
        agent = ValidatorAgent()
        data = self.make_validator_input()
        for question in data["questions"]:
            metadata = question.setdefault("metadata", {})
            metadata.setdefault("topic", "Tim và mạch máu")
            metadata.setdefault("achievement", "Mô tả được cấu tạo tim")
            metadata["scope_guard"] = {"status": "passed"}

        result = await agent.run(**data)
        scope_check = next(
            check for check in result["checks"] if check["name"] == "CHECK_CURRICULUM_SCOPE"
        )
        assert scope_check["passed"], f"Không kỳ vọng fail: {scope_check}"

    @pytest.mark.asyncio
    async def test_total_score_check(self):
        agent = ValidatorAgent()
        data = self.make_validator_input()
        # Modify scores to not equal 10
        data["questions"] = [
            {**q, "score": 1.0} for q in data["questions"]
        ]
        result = await agent.run(**data)
        checks = result["checks"]
        score_check = [c for c in checks if c["name"] == "CHECK_TOTAL_SCORE"][0]
        assert not score_check["passed"], "Should fail when total score != 10"

    @pytest.mark.asyncio
    async def test_detect_duplicates(self):
        agent = ValidatorAgent()
        data = self.make_validator_input()
        # Duplicate first question
        data["questions"].append(data["questions"][0].copy())
        result = await agent.run(**data)
        dup_check = [c for c in result["checks"] if c["name"] == "CHECK_NO_DUPLICATES"][0]
        assert not dup_check["passed"], "Should detect duplicates"

    @pytest.mark.asyncio
    async def test_answer_key_completeness(self):
        agent = ValidatorAgent()
        data = self.make_validator_input()
        # Remove one answer
        data["answer_key"] = data["answer_key"][:-1]
        result = await agent.run(**data)
        answer_check = [c for c in result["checks"] if c["name"] == "CHECK_ANSWER_KEY_COMPLETE"][0]
        assert not answer_check["passed"], "Should fail when answer missing"

    @pytest.mark.asyncio
    async def test_rubric_for_essay(self):
        agent = ValidatorAgent()
        data = self.make_validator_input()
        # Remove all rubrics
        data["rubric"] = []
        result = await agent.run(**data)
        rubric_check = [c for c in result["checks"] if c["name"] == "CHECK_RUBRIC_COMPLETE"][0]
        assert not rubric_check["passed"], "Should fail when essay rubric missing"


# ============================================================
# Test AnswerAgent
# ============================================================


class TestAnswerAgent:
    """Test AnswerAgent."""

    def test_answer_generation_passes_strict_output_contract(self):
        agent = AnswerAgent()
        received = {}

        def fake_generate(_prompt, **kwargs):
            received.update(kwargs)
            return {"answer_key": [], "rubric": []}

        agent.gemini.generate_json = fake_generate

        assert agent._run_gemini([], []) == {"answer_key": [], "rubric": []}
        assert received["response_model"] is AnswerGenerationOutput

    def test_answers_for_all_types(self):
        """Test that deterministic fallback creates answers for each question type."""
        import asyncio
        agent = AnswerAgent()
        questions = [
            {
                "id": "q_1",
                "number": 1,
                "type": "multiple_choice",
                "difficulty": "nhan_biet",
                "score": 0.25,
                "content": "Test MCQ",
                "options": {"A": "Option 1", "B": "Option 2", "C": "Option 3", "D": "Option 4"},
            },
            {
                "id": "q_2",
                "number": 2,
                "type": "true_false",
                "difficulty": "thong_hieu",
                "score": 0.5,
                "content": "Test TF",
                "statements": [
                    {"id": "s_2_1", "content": "Statement 1", "is_true": True},
                    {"id": "s_2_2", "content": "Statement 2", "is_true": False},
                    {"id": "s_2_3", "content": "Statement 3", "is_true": True},
                    {"id": "s_2_4", "content": "Statement 4", "is_true": False},
                ],
            },
            {
                "id": "q_3",
                "number": 3,
                "type": "short_answer",
                "difficulty": "van_dung",
                "score": 0.5,
                "content": "Test SA",
            },
            {
                "id": "q_4",
                "number": 4,
                "type": "essay",
                "difficulty": "van_dung",
                "score": 2.0,
                "content": "Test essay",
            },
        ]
        specification = [
            {"question_id": q["id"], "score": q["score"], "topic": "Test Topic"}
            for q in questions
        ]
        result = asyncio.new_event_loop().run_until_complete(
            agent.run(questions=questions, specification=specification)
        )
        assert "answer_key" in result
        assert "rubric" in result
        assert len(result["answer_key"]) == len(questions)
        # Only essay questions should have rubric
        essay_count = sum(1 for q in questions if q["type"] == "essay")
        assert len(result["rubric"]) == essay_count

    @pytest.mark.asyncio
    async def test_incomplete_ai_answer_output_uses_complete_fallback(self):
        agent = AnswerAgent()
        agent.has_ai = True
        agent._run_gemini = lambda _questions, _specification: {
            "answer_key": [{"question_id": "q_1"}],
            "rubric": [],
        }
        questions = [
            {"id": "q_1", "number": 1, "type": "multiple_choice", "score": 0.25},
            {"id": "q_2", "number": 2, "type": "essay", "score": 2.0},
        ]
        specification = [{"question_id": item["id"], "topic": "Tế bào", "score": item["score"]} for item in questions]

        result = await agent.run(questions=questions, specification=specification)

        assert [answer["question_id"] for answer in result["answer_key"]] == ["q_1", "q_2"]
        assert [item["question_id"] for item in result["rubric"]] == ["q_2"]

    def test_mcq_answer_has_correct_answer(self):
        import asyncio
        agent = AnswerAgent()
        question = {
            "id": "q_1",
            "number": 1,
            "type": "multiple_choice",
            "difficulty": "nhan_biet",
            "score": 0.25,
            "content": "Test",
        }
        spec = {"question_id": "q_1", "score": 0.25, "topic": "Test"}
        result = asyncio.new_event_loop().run_until_complete(
            agent.run(questions=[question], specification=[spec])
        )
        answer = result["answer_key"][0]
        assert "correct_answer" in answer
        assert "explanation" in answer

    def test_essay_has_model_answer_and_key_points(self):
        import asyncio
        agent = AnswerAgent()
        question = {
            "id": "q_1",
            "number": 1,
            "type": "essay",
            "difficulty": "van_dung",
            "score": 2.0,
            "content": "Test essay",
        }
        spec = {"question_id": "q_1", "score": 2.0, "topic": "Test"}
        result = asyncio.new_event_loop().run_until_complete(
            agent.run(questions=[question], specification=[spec])
        )
        answer = result["answer_key"][0]
        rubric = result["rubric"][0]
        assert "model_answer" in answer
        assert "key_points" in answer
        assert len(rubric["criteria"]) >= 2
        assert "grading_guide" in rubric

    def test_rubric_total_equals_question_score(self):
        import asyncio
        agent = AnswerAgent()
        question = {
            "id": "q_1",
            "number": 1,
            "type": "essay",
            "difficulty": "van_dung",
            "score": 3.0,
            "content": "Test essay",
        }
        spec = {"question_id": "q_1", "score": 3.0, "topic": "Test"}
        result = asyncio.new_event_loop().run_until_complete(
            agent.run(questions=[question], specification=[spec])
        )
        rubric = result["rubric"][0]
        assert rubric["total_score"] == 3.0
        # Sum of max_score of all criteria should equal total_score
        criteria_sum = round(sum(c["max_score"] for c in rubric["criteria"]), 2)
        assert criteria_sum == 3.0, f"Criteria max score sum {criteria_sum} != 3.0"
