from copy import deepcopy
from typing import get_args

import pytest
from fastapi import HTTPException

from app.agents.question_agent import QuestionAgent
from app.agents.specification_agent import SpecificationAgent
from app.agents.verification_agent import VerificationAgent
from app.core.config import settings
from app.schemas.ai_outputs import GeneratedCalculation
from app.services.exam.generation_planning import build_generation_plan, parse_learning_objective
from app.services.exam.formula_registry import (
    FORMULA_CAPABILITIES,
    allowed_formula_ids,
    capability_issues,
)
from app.services.exam.grounding import apply_local_sources
from app.services.exam.numerical_verifier import SOLVERS, solve_calculation, validate_calculation
from app.services.exam.semantic_validation import blocking_issues, validate_generated_item
from app.services.exam_service import ExamService


def spec(
    objective,
    *,
    topic="Hệ tuần hoàn ở người",
    question_type="multiple_choice",
    difficulty="thong_hieu",
    source_context="Tim co bóp tạo lực đẩy giúp máu lưu thông liên tục trong hệ mạch.",
):
    return {
        "question_id": "q_1",
        "question_number": 1,
        "question_type": question_type,
        "difficulty": difficulty,
        "score": 1.0,
        "topic": topic,
        "lesson": topic,
        "knowledge_unit": topic,
        "achievement": objective,
        "bloom_level": {"nhan_biet": "remember", "thong_hieu": "understand", "van_dung": "apply"}[difficulty],
        "source_context": source_context,
        "source": {
            "source_type": "rag_retrieval",
            "source_name": "SGK KHTN 8.pdf",
            "source_excerpt": source_context,
            "doc_id": 1,
            "retrieved_chunk_id": "chunk-1",
        },
    }


def valid_function_mc():
    question = {
        "id": "q_1",
        "number": 1,
        "type": "multiple_choice",
        "difficulty": "thong_hieu",
        "score": 1.0,
        "content": "Chức năng chủ yếu của tim người trong hệ tuần hoàn là gì?",
        "options": {
            "A": "Co bóp tạo lực đẩy giúp máu lưu thông trong hệ mạch.",
            "B": "Thực hiện trao đổi khí oxygen và carbon dioxide với môi trường.",
            "C": "Lọc chất thải hòa tan ra khỏi máu để tạo thành nước tiểu.",
            "D": "Tiêu hóa thức ăn thành các chất dinh dưỡng có thể hấp thụ.",
        },
        "correct_answer": "A",
    }
    answer = {
        "question_id": "q_1",
        "question_number": 1,
        "type": "multiple_choice",
        "correct_answer": "A",
        "explanation": "Tim co bóp nhịp nhàng tạo chênh lệch áp lực, nhờ đó máu được đẩy qua động mạch, mao mạch, tĩnh mạch rồi trở về tim.",
        "option_explanations": {
            "A": "Đúng vì lực co bóp của tim duy trì dòng máu trong hệ mạch.",
            "B": "Sai vì trao đổi khí với môi trường là chức năng chính của hệ hô hấp.",
            "C": "Sai vì lọc máu và tạo nước tiểu là chức năng của hệ bài tiết, chủ yếu ở thận.",
            "D": "Sai vì biến đổi thức ăn là chức năng của hệ tiêu hóa, không phải của tim.",
        },
    }
    return question, answer


def test_a_biology_factual_plan_extracts_scientific_target_not_objective():
    objective = "Mô tả được cấu tạo và chức năng của tim người trong hệ tuần hoàn."
    parsed = parse_learning_objective(objective)
    plan = build_generation_plan(spec(objective), grade=8)

    assert parsed["action"] == "mô tả"
    assert parsed["knowledge_objects"] == [
        "cấu tạo của tim người trong hệ tuần hoàn",
        "chức năng của tim người trong hệ tuần hoàn",
    ]
    assert not plan.knowledge_target.lower().startswith("mô tả được")
    assert plan.domain == "biology_like"
    assert plan.knowledge_intent == "structure"
    assert plan.reasoning_mode == "factual"


@pytest.mark.parametrize(
    ("objective", "topic", "source_context"),
    [
        (
            "Trình bày được khái niệm quang hợp và điều kiện quang hợp.",
            "Quang hợp ở thực vật",
            "Tìm hiểu về quá trình quang hợp ở thực vật và vai trò của quang hợp.",
        ),
        (
            "Trình bày được khái niệm hô hấp tế bào.",
            "Hô hấp tế bào",
            "Tìm hiểu về hô hấp tế bào và vai trò của hô hấp trong cơ thể.",
        ),
    ],
)
def test_intent_prefers_objective_target_over_broader_source_summary(
    objective, topic, source_context
):
    plan = build_generation_plan(
        spec(objective, topic=topic, source_context=source_context),
        grade=7,
    )

    assert plan.knowledge_intent == "definition"
    assert plan.reasoning_mode == "factual"


def test_equation_objective_is_not_reclassified_by_source_summary_role_text():
    plan = build_generation_plan(
        spec(
            "Viết được phương trình quang hợp ở mức đơn giản.",
            topic="Quang hợp ở thực vật",
            source_context=(
                "Tìm hiểu về quá trình quang hợp ở thực vật và vai trò của quang hợp."
            ),
        ),
        grade=7,
    )

    assert plan.knowledge_intent == "identification"
    assert plan.reasoning_mode == "factual"


@pytest.mark.parametrize(
    "content",
    [
        "Đâu là đặc điểm đúng về đồng hóa so với dị hóa ở sinh vật?",
        "Điểm khác biệt cơ bản giữa đồng hóa và dị hóa ở sinh vật là gì?",
    ],
)
def test_comparison_intent_accepts_equivalent_teacher_wording(content):
    item = spec(
        "Phân biệt được đồng hóa và dị hóa.",
        topic="Trao đổi chất và chuyển hóa năng lượng ở sinh vật",
        source_context=(
            "Đồng hóa tổng hợp chất và tích lũy năng lượng; dị hóa phân giải chất "
            "và giải phóng năng lượng."
        ),
    )
    plan = build_generation_plan(item, grade=7)
    question = {
        "id": "q_1",
        "number": 1,
        "type": "multiple_choice",
        "content": content,
        "options": {
            "A": "Đồng hóa tổng hợp chất và tích lũy năng lượng, còn dị hóa phân giải chất và giải phóng năng lượng.",
            "B": "Đồng hóa và dị hóa đều chỉ phân giải chất để giải phóng năng lượng.",
            "C": "Đồng hóa chỉ xảy ra ở thực vật, còn dị hóa chỉ xảy ra ở động vật.",
            "D": "Đồng hóa không cần năng lượng, còn dị hóa luôn tích lũy năng lượng.",
        },
        "correct_answer": "A",
    }
    answer = {
        "question_id": "q_1",
        "question_number": 1,
        "type": "multiple_choice",
        "correct_answer": "A",
        "explanation": (
            "Đồng hóa tạo chất phức tạp và tích lũy năng lượng, trong khi dị hóa "
            "phân giải chất phức tạp và giải phóng năng lượng cho tế bào."
        ),
        "option_explanations": {
            "A": "Đúng vì mô tả chính xác chiều biến đổi vật chất và năng lượng của hai quá trình.",
            "B": "Sai vì đồng hóa là quá trình tổng hợp, không phải quá trình phân giải chất.",
            "C": "Sai vì cả đồng hóa và dị hóa đều diễn ra trong tế bào của thực vật lẫn động vật.",
            "D": "Sai vì đồng hóa cần năng lượng, còn dị hóa là quá trình giải phóng năng lượng.",
        },
    }

    issue_codes = {
        issue.code
        for issue in validate_generated_item(
            question=question,
            answer=answer,
            rubric=None,
            spec=item,
            plan=plan,
        )
    }

    assert "knowledge_intent_mismatch" not in issue_codes


def test_true_false_comparison_can_be_expressed_across_child_statements():
    item = spec(
        "Phân biệt được sinh trưởng ở thực vật và động vật.",
        topic="Sinh trưởng và phát triển ở sinh vật",
        question_type="true_false",
        source_context=(
            "Thực vật thường sinh trưởng suốt đời tại mô phân sinh; động vật "
            "thường sinh trưởng đến một giới hạn xác định."
        ),
    )
    plan = build_generation_plan(item, grade=7)
    statements = [
        {
            "id": "s_1_1",
            "content": "Sinh trưởng ở thực vật thường diễn ra suốt đời và tập trung tại mô phân sinh.",
            "is_true": True,
        },
        {
            "id": "s_1_2",
            "content": "Ở động vật, sinh trưởng chỉ diễn ra khi còn là phôi rồi dừng hoàn toàn.",
            "is_true": False,
        },
        {
            "id": "s_1_3",
            "content": "Sinh trưởng của động vật chịu ảnh hưởng của hormone và môi trường.",
            "is_true": True,
        },
        {
            "id": "s_1_4",
            "content": "Sinh trưởng của thực vật và động vật đều chịu ảnh hưởng của di truyền.",
            "is_true": True,
        },
    ]
    question = {
        "id": "q_1",
        "number": 1,
        "type": "true_false",
        "content": "Xác định đúng hoặc sai các phát biểu về sinh trưởng ở thực vật và động vật.",
        "statements": statements,
    }
    answer = {
        "question_id": "q_1",
        "question_number": 1,
        "type": "true_false",
        "answers": [
            {
                "statement_id": statement["id"],
                "is_true": statement["is_true"],
                "explanation": (
                    "Đúng vì phát biểu mô tả phù hợp đặc điểm sinh trưởng của nhóm sinh vật này."
                    if statement["is_true"]
                    else "Sai vì sinh trưởng ở động vật còn tiếp tục sau giai đoạn phôi và chỉ dừng ở giới hạn xác định."
                ),
            }
            for statement in statements
        ],
    }

    issue_codes = {
        issue.code
        for issue in validate_generated_item(
            question=question,
            answer=answer,
            rubric=None,
            spec=item,
            plan=plan,
        )
    }

    assert "knowledge_intent_mismatch" not in issue_codes


def test_cause_effect_cannot_degrade_into_identification_question():
    item = spec(
        "Giải thích được ảnh hưởng của hoạt động thể lực đến trao đổi chất.",
        topic="Trao đổi chất và chuyển hóa năng lượng ở sinh vật",
        question_type="short_answer",
        source_context=(
            "Hoạt động thể lực làm tăng nhu cầu năng lượng, nhịp tim và nhịp thở, "
            "từ đó tăng cung cấp oxygen và chất dinh dưỡng cho tế bào."
        ),
    )
    plan = build_generation_plan(item, grade=7)
    question = {
        "id": "q_1",
        "number": 1,
        "type": "short_answer",
        "content": (
            "Kể tên một yếu tố bên ngoài cơ thể tăng lên khi hoạt động thể lực, "
            "làm thúc đẩy quá trình trao đổi chất ở sinh vật."
        ),
    }
    answer = {
        "question_id": "q_1",
        "question_number": 1,
        "type": "short_answer",
        "correct_answer": "nhịp tim",
        "explanation": (
            "Hoạt động thể lực làm tăng nhịp tim, nhờ đó oxygen và chất dinh dưỡng "
            "được vận chuyển tới tế bào nhanh hơn."
        ),
    }

    issue_codes = {
        issue.code
        for issue in validate_generated_item(
            question=question,
            answer=answer,
            rubric=None,
            spec=item,
            plan=plan,
        )
    }

    assert "knowledge_intent_mismatch" in issue_codes
    assert "không đổi thành câu kể tên" in QuestionAgent.INTENT_STEM_GUIDANCE["cause_effect"]


def test_cause_effect_accepts_closed_directional_short_answer():
    item = spec(
        "Giải thích được ảnh hưởng của hoạt động thể lực đến trao đổi chất.",
        topic="Trao đổi chất và chuyển hóa năng lượng ở sinh vật",
        question_type="short_answer",
        source_context=(
            "Hoạt động thể lực làm tăng nhu cầu năng lượng và tốc độ trao đổi chất."
        ),
    )
    question = {
        "id": "q_1",
        "number": 1,
        "type": "short_answer",
        "content": (
            "Khi hoạt động thể lực tăng, tốc độ trao đổi chất ở cơ thể người "
            "sẽ tăng hay giảm? Trả lời bằng một từ."
        ),
    }
    answer = {
        "question_id": "q_1",
        "question_number": 1,
        "type": "short_answer",
        "correct_answer": "tăng",
        "explanation": (
            "Hoạt động thể lực làm nhu cầu năng lượng tăng nên cơ thể tăng "
            "tốc độ trao đổi chất để cung cấp đủ năng lượng."
        ),
    }

    issue_codes = {
        issue.code
        for issue in validate_generated_item(
            question=question,
            answer=answer,
            rubric=None,
            spec=item,
            plan=build_generation_plan(item, grade=7),
        )
    }

    assert "knowledge_intent_mismatch" not in issue_codes


@pytest.mark.parametrize(
    ("objective", "topic", "source_context", "content", "correct_answer"),
    [
        (
            "Thiết kế được thí nghiệm chứng minh quang hợp cần ánh sáng và CO2.",
            "Quang hợp ở thực vật",
            "Thí nghiệm thay đổi ánh sáng giữa mẫu thử và mẫu đối chứng rồi kiểm tra tinh bột.",
            (
                "Trong thí nghiệm quang hợp, biến nào được thay đổi giữa chậu ngoài sáng và "
                "chậu trong tối? Trả lời bằng một từ hoặc cụm từ ngắn."
            ),
            "ánh sáng",
        ),
        (
            "Giải thích được ảnh hưởng của hoạt động thể lực đến trao đổi chất.",
            "Trao đổi chất và chuyển hóa năng lượng ở sinh vật",
            "Hoạt động thể lực làm tăng nhu cầu năng lượng và tốc độ trao đổi chất.",
            (
                "Nguyên nhân trực tiếp nào tăng khi hoạt động thể lực, làm trao đổi chất diễn "
                "ra nhanh hơn? Trả lời bằng một cụm từ ngắn."
            ),
            "nhu cầu năng lượng",
        ),
    ],
)
def test_short_answer_uses_one_canonical_scientific_term(
    objective, topic, source_context, content, correct_answer
):
    item = spec(
        objective,
        topic=topic,
        question_type="short_answer",
        source_context=source_context,
    )
    plan = build_generation_plan(item, grade=7)
    question = {
        "id": "q_1",
        "number": 1,
        "type": "short_answer",
        "content": content,
    }
    answer = {
        "question_id": "q_1",
        "question_number": 1,
        "type": "short_answer",
        "correct_answer": correct_answer,
        "explanation": (
            "Đáp án xác định đúng đại lượng khoa học trực tiếp được yêu cầu trong tình huống."
        ),
    }

    assert blocking_issues(
        validate_generated_item(
            question=question,
            answer=answer,
            rubric=None,
            spec=item,
            plan=plan,
        )
    ) == []
    tailored_guidance = QuestionAgent.SHORT_ANSWER_INTENT_GUIDANCE[
        plan.knowledge_intent
    ]
    assert (
        "từ/cụm từ ngắn" in tailored_guidance
        or "tối đa năm từ" in tailored_guidance
        or "tăng hay giảm" in tailored_guidance
    )


@pytest.mark.asyncio
async def test_specification_rotates_learning_objectives_instead_of_reusing_first():
    lesson = type(
        "Lesson",
        (),
        {
            "topic": "Hệ tuần hoàn ở người",
            "achievements": [
                "Mô tả được cấu tạo của tim người.",
                "Nêu được chức năng của tim người.",
                "Phân biệt được động mạch và tĩnh mạch.",
            ],
        },
    )()
    plan = [
        {
            "lesson_index": 0,
            "difficulty": "thong_hieu",
            "type": "multiple_choice",
            "score": 0.25,
            "question_id": f"q_{index}",
        }
        for index in range(1, 4)
    ]

    rows = await SpecificationAgent().run(matrix=[], question_plan=plan, curriculum=[lesson])

    assert [row["achievement"] for row in rows] == lesson.achievements
    assert rows[0]["knowledge_unit"] == "cấu tạo của tim người"


def test_b_biology_data_plan_is_quantitative_without_becoming_physics():
    item = spec(
        "Phân tích được bảng số liệu về sự thay đổi nhịp tim khi vận động.",
        topic="Tuần hoàn ở người",
        difficulty="van_dung",
        source_context="| Trạng thái | Nhịp tim (nhịp/phút) |\n|---|---:|\n| Nghỉ | 72 |\n| Sau vận động | 108 |",
    )
    plan = build_generation_plan(item, grade=8)

    assert plan.domain == "biology_like"
    assert plan.knowledge_intent == "data_interpretation"
    assert plan.reasoning_mode == "data_analysis"
    assert "read_presented_data" in plan.required_skills


def speed_calculation(result=5.0):
    return {
        "formula_id": "SPEED",
        "known_values": [
            {"symbol": "s", "value": 1.5, "unit": "km"},
            {"symbol": "t", "value": 5, "unit": "min"},
        ],
        "target_symbol": "v",
        "calculation_steps": ["1,5 km = 1500 m", "5 min = 300 s", "v = 1500 / 300"],
        "result": {"value": result, "unit": "m/s"},
        "rounding_decimals": None,
    }


def speed_question(options=None, correct="A"):
    return {
        "id": "q_1",
        "number": 1,
        "type": "multiple_choice",
        "content": "Một vật đi được 1,5 km trong 5 phút. Tính tốc độ của vật theo m/s.",
        "options": options or {"A": "5 m/s", "B": "300 m/s", "C": "0,3 m/s", "D": "30 m/s"},
        "correct_answer": correct,
    }


def test_c_speed_calculation_converts_units_and_rejects_wrong_result():
    expected, unit, relationship = solve_calculation(speed_calculation())
    assert float(expected) == 5
    assert unit == "m/s"
    assert relationship == "v = s / t"
    assert validate_calculation(speed_calculation(), speed_question(), {"correct_answer": "A"}) == []

    issues = validate_calculation(speed_calculation(300), speed_question(), {"correct_answer": "A"})
    assert "numeric_result_mismatch" in {issue.code for issue in issues}


def test_c_speed_formula_rearrangement_calculates_distance():
    calculation = {
        "formula_id": "SPEED",
        "known_values": [
            {"symbol": "v", "value": 5, "unit": "m/s"},
            {"symbol": "t", "value": 1, "unit": "min"},
        ],
        "target_symbol": "s",
        "calculation_steps": ["s = v × t"],
        "result": {"value": 300, "unit": "m"},
        "rounding_decimals": None,
    }
    expected, unit, relationship = solve_calculation(calculation)
    assert float(expected) == 300
    assert unit == "m"
    assert relationship == "s = v × t"


def test_c_equivalent_speed_options_fail_single_choice():
    question = speed_question(
        {"A": "5 m/s", "B": "18 km/h", "C": "0,3 m/s", "D": "300 m/s"}
    )
    issues = validate_calculation(speed_calculation(), question, {"correct_answer": "A"})
    assert "numeric_correct_option_count" in {issue.code for issue in issues}


def test_c_scientific_sanity_rejects_impossible_walking_speed():
    calculation = speed_calculation(5000)
    calculation["known_values"] = [
        {"symbol": "s", "value": 5000, "unit": "m"},
        {"symbol": "t", "value": 1, "unit": "s"},
    ]
    question = speed_question(
        {"A": "5000 m/s", "B": "50 m/s", "C": "5 m/s", "D": "0,5 m/s"}
    )
    question["content"] = "Một học sinh đi bộ 5000 m trong 1 s. Tính tốc độ."
    issues = validate_calculation(calculation, question, {"correct_answer": "A"})
    assert "scientific_sanity_speed" in {issue.code for issue in issues}


def test_quantitative_formula_must_match_target_or_controlled_source():
    item = spec(
        "Nêu được chức năng của tim người.",
        source_context="Tim co bóp tạo lực đẩy máu qua hệ mạch.",
    )
    plan = build_generation_plan(item, grade=8)
    plan = plan.__class__(
        **{
            **plan.as_prompt_dict(),
            "knowledge_intent": "calculation",
            "reasoning_mode": "quantitative",
        }
    )
    question = speed_question()
    question["content"] = "Tính một đại lượng về chức năng của tim người."
    _, answer = valid_function_mc()

    issues = validate_generated_item(
        question=question,
        answer=answer,
        rubric=None,
        spec=item,
        plan=plan,
        calculation=speed_calculation(),
    )

    assert "formula_not_grounded" in {issue.code for issue in issues}


def test_d_physics_conceptual_is_not_forced_to_calculation():
    plan = build_generation_plan(
        spec(
            "Giải thích được hiện tượng phản xạ ánh sáng.",
            topic="Ánh sáng",
            source_context="Ánh sáng bị đổi hướng và trở lại môi trường cũ khi gặp mặt phản xạ.",
        ),
        grade=7,
    )
    assert plan.domain == "physics_like"
    assert plan.knowledge_intent in {"cause_effect", "explanation"}
    assert plan.reasoning_mode == "causal"


def test_e_chemistry_factual_property_plan():
    plan = build_generation_plan(
        spec(
            "Nêu được tính chất vật lí của oxygen.",
            topic="Oxygen và không khí",
            source_context="Oxygen là chất khí không màu, không mùi và ít tan trong nước.",
        ),
        grade=6,
    )
    assert plan.domain == "chemistry_like"
    assert plan.knowledge_intent == "property"
    assert plan.reasoning_mode == "factual"


def test_f_chemistry_quantitative_plan_uses_math_cross_cutting():
    plan = build_generation_plan(
        spec(
            "Tính được nồng độ phần trăm của dung dịch.",
            topic="Dung dịch và nồng độ dung dịch",
            difficulty="van_dung",
            source_context="Nồng độ phần trăm cho biết số gam chất tan có trong 100 gam dung dịch.",
        ),
        grade=8,
    )
    assert plan.domain == "chemistry_like"
    assert plan.knowledge_intent == "calculation"
    assert plan.reasoning_mode == "quantitative"
    assert "normalize_units" in plan.required_skills

    calculation = {
        "formula_id": "CONCENTRATION_PERCENT",
        "known_values": [
            {"symbol": "m_solute", "value": 10, "unit": "g"},
            {"symbol": "m_solution", "value": 200, "unit": "g"},
        ],
        "target_symbol": "concentration",
        "calculation_steps": ["C% = 10 / 200 × 100%"],
        "result": {"value": 5, "unit": "%"},
        "rounding_decimals": None,
    }
    question = {
        "type": "multiple_choice",
        "options": {"A": "5%", "B": "10%", "C": "20%", "D": "0,5%"},
        "correct_answer": "A",
    }
    assert validate_calculation(calculation, question, {"correct_answer": "A"}) == []


def test_g_experiment_plan_is_selected_from_intent_not_domain():
    plan = build_generation_plan(
        spec(
            "Thực hiện được thí nghiệm chứng minh cây cần ánh sáng để quang hợp.",
            topic="Quang hợp ở thực vật",
            difficulty="van_dung",
            source_context="Thí nghiệm cần có mẫu được chiếu sáng và mẫu đối chứng không được chiếu sáng.",
        ),
        grade=7,
    )
    assert plan.domain == "biology_like"
    assert plan.knowledge_intent == "experiment"
    assert plan.reasoning_mode == "experimental"


def test_h_application_plan_requires_real_application_reasoning():
    plan = build_generation_plan(
        spec(
            "Vận dụng được kiến thức về truyền nhiệt để giữ ấm cơ thể.",
            topic="Nhiệt",
            difficulty="van_dung",
            source_context="Vật liệu dẫn nhiệt kém làm giảm tốc độ truyền nhiệt từ cơ thể ra môi trường.",
        ),
        grade=8,
    )
    assert plan.knowledge_intent == "application"
    assert plan.reasoning_mode == "application"


def test_i_true_false_keeps_children_and_requires_false_correction():
    item = spec(
        "Phân biệt được động mạch, tĩnh mạch và mao mạch.",
        question_type="true_false",
        source_context="Động mạch dẫn máu từ tim đi; tĩnh mạch đưa máu về tim; mao mạch nối hai hệ mạch.",
    )
    plan = build_generation_plan(item, grade=8)
    question = {
        "id": "q_1",
        "number": 1,
        "type": "true_false",
        "content": "Phân biệt động mạch, tĩnh mạch và mao mạch qua các phát biểu trong hệ tuần hoàn người.",
        "statements": [
            {"id": "s1", "content": "Động mạch dẫn máu từ tim đến các cơ quan trong cơ thể.", "is_true": True},
            {"id": "s2", "content": "Tĩnh mạch dẫn máu từ tim đến các cơ quan trong cơ thể.", "is_true": False},
            {"id": "s3", "content": "Mao mạch là nơi trao đổi chất giữa máu và tế bào.", "is_true": True},
            {"id": "s4", "content": "Mọi động mạch đều vận chuyển máu giàu oxygen.", "is_true": False},
        ],
    }
    answer = {
        "question_id": "q_1",
        "type": "true_false",
        "answers": [
            {"statement_id": "s1", "is_true": True, "explanation": "Đúng. Động mạch được xác định theo chiều dẫn máu rời khỏi tim."},
            {"statement_id": "s2", "is_true": False, "explanation": "Sai ở chiều vận chuyển; tĩnh mạch đưa máu từ các cơ quan trở về tim."},
            {"statement_id": "s3", "is_true": True, "explanation": "Đúng. Thành mao mạch mỏng tạo điều kiện trao đổi chất với tế bào."},
            {"statement_id": "s4", "is_true": False, "explanation": "Sai ở từ mọi; động mạch phổi đưa máu nghèo oxygen từ tim đến phổi."},
        ],
    }
    issues = validate_generated_item(question=question, answer=answer, rubric=None, spec=item, plan=plan)
    assert blocking_issues(issues) == []
    assert len(question["statements"]) == 4
    assert QuestionAgent.FALSE_STATEMENT_CORRECTION_FORMAT.startswith("Sai vì")
    assert "đúng là" in QuestionAgent.FALSE_STATEMENT_CORRECTION_FORMAT


def test_j_essay_expected_answer_and_rubric_contain_scientific_ideas():
    item = spec(
        "Trình bày được cấu tạo và chức năng của tim người.",
        question_type="essay",
        difficulty="thong_hieu",
        source_context="Tim người có bốn ngăn; thành tim co bóp tạo lực đẩy máu qua hệ mạch.",
    )
    plan = build_generation_plan(item, grade=8)
    question = {
        "id": "q_1",
        "number": 1,
        "type": "essay",
        "content": "Trình bày cấu tạo của tim người và giải thích cấu tạo đó hỗ trợ chức năng bơm máu như thế nào.",
    }
    answer = {
        "question_id": "q_1",
        "type": "essay",
        "model_answer": "Tim người gồm bốn ngăn: hai tâm nhĩ ở phía trên và hai tâm thất ở phía dưới. Thành tâm thất có cơ phát triển; sự co bóp nhịp nhàng của cơ tim tạo lực đẩy máu qua hệ mạch.",
        "key_points": [
            "Tim người gồm hai tâm nhĩ và hai tâm thất.",
            "Cơ tim co bóp tạo lực đẩy máu qua hệ mạch.",
        ],
    }
    rubric = {
        "criteria": [
            {"name": "Cấu tạo", "max_score": 0.5, "levels": [{"score": 0.5, "description": "Nêu đủ bốn ngăn", "criteria": "Hai tâm nhĩ, hai tâm thất"}]},
            {"name": "Liên hệ cấu tạo - chức năng", "max_score": 0.5, "levels": [{"score": 0.5, "description": "Giải thích lực co bóp", "criteria": "Cơ tim tạo lực đẩy máu"}]},
        ]
    }
    issues = validate_generated_item(question=question, answer=answer, rubric=rubric, spec=item, plan=plan)
    assert blocking_issues(issues) == []


def test_regression_rejects_learning_objective_and_meta_distractors():
    item = spec("Mô tả được cấu tạo và chức năng của tim người trong hệ tuần hoàn.")
    plan = build_generation_plan(item, grade=8)
    question = {
        "id": "q_1",
        "number": 1,
        "type": "multiple_choice",
        "content": "Về khái niệm cơ bản của hệ tuần hoàn, hãy chọn nhận định đúng.",
        "options": {
            "A": item["achievement"],
            "B": "Có thể bỏ qua khái niệm cơ bản.",
            "C": "Khái niệm cơ bản luôn cho kết quả giống nhau.",
            "D": "Chỉ cần ghi nhớ tên gọi.",
        },
        "correct_answer": "A",
    }
    answer = {
        "correct_answer": "A",
        "explanation": "Phương án A phù hợp với yêu cầu cần đạt và các phương án khác không phù hợp với yêu cầu.",
        "option_explanations": {label: "Phương án này phù hợp với yêu cầu cần đạt." for label in "ABCD"},
    }
    issues = validate_generated_item(question=question, answer=answer, rubric=None, spec=item, plan=plan)
    codes = {issue.code for issue in blocking_issues(issues)}
    assert "learning_objective_copy" in codes
    assert "meta_learning_language" in codes


def test_instructional_verb_in_scientific_marking_point_is_not_objective_copy():
    item = spec(
        "Nêu được mối quan hệ giữa quang hợp và hô hấp trong tự nhiên.",
        topic="Hô hấp tế bào",
        question_type="essay",
    )
    plan = build_generation_plan(item, grade=7)
    question = {
        "id": "q_1",
        "number": 1,
        "type": "essay",
        "content": (
            "Phân tích sự trao đổi vật chất giữa quang hợp và hô hấp tế bào "
            "trong một hệ sinh thái."
        ),
    }
    answer = {
        "question_id": "q_1",
        "type": "essay",
        "model_answer": (
            "Quang hợp sử dụng carbon dioxide và tạo oxygen, còn hô hấp sử dụng "
            "oxygen và giải phóng carbon dioxide. Sản phẩm của quá trình này là "
            "nguyên liệu của quá trình kia nên vật chất được tuần hoàn."
        ),
        "key_points": [
            "Nêu được quang hợp hấp thụ carbon dioxide và tạo oxygen.",
            "Nêu được hô hấp sử dụng oxygen và thải carbon dioxide.",
        ],
    }
    rubric = {
        "criteria": [
            {"name": "Quang hợp", "max_score": 1.0},
            {"name": "Hô hấp", "max_score": 1.0},
        ]
    }

    issues = validate_generated_item(
        question=question,
        answer=answer,
        rubric=rubric,
        spec=item,
        plan=plan,
    )

    assert "learning_objective_copy" not in {issue.code for issue in issues}


def test_data_reference_without_table_or_image_is_rejected():
    item = spec(
        "Phân tích được bảng số liệu về nhịp tim.",
        source_context="Nhịp tim được đo ở trạng thái nghỉ và sau vận động.",
    )
    plan = build_generation_plan(item, grade=8)
    question, answer = valid_function_mc()
    question["content"] = "Quan sát bảng dưới đây và nhận xét sự thay đổi nhịp tim."
    issues = validate_generated_item(question=question, answer=answer, rubric=None, spec=item, plan=plan)
    assert "referenced_material_missing" in {issue.code for issue in issues}


@pytest.mark.asyncio
async def test_generation_retries_with_explicit_semantic_failure_codes(monkeypatch):
    agent = QuestionAgent()
    agent.has_ai = True
    item = spec("Nêu được chức năng của tim người.")
    calls = []
    good_question, good_answer = valid_function_mc()

    def fake_run(batch, grade, failures):
        calls.append(deepcopy(failures))
        if len(calls) == 1:
            bad_question = deepcopy(good_question)
            bad_question["options"]["A"] = item["achievement"]
            bad_answer = deepcopy(good_answer)
            bad_answer["explanation"] = "Phù hợp với yêu cầu cần đạt nên đáp án A đúng."
            return {"questions": [bad_question], "answer_key": [bad_answer], "rubric": []}
        return {"questions": [deepcopy(good_question)], "answer_key": [deepcopy(good_answer)], "rubric": []}

    monkeypatch.setattr(agent, "_run_gemini", fake_run)
    result = await agent.run(specification=[item], grade=8)

    assert len(calls) == 2
    assert "learning_objective_copy" in calls[1]["q_1"]
    assert result["questions"][0]["content"].startswith("Chức năng")


@pytest.mark.asyncio
async def test_generation_retry_isolates_only_failed_question_ids(monkeypatch):
    agent = QuestionAgent()
    agent.has_ai = True
    first = spec("Nêu được chức năng của tim người.")
    second = deepcopy(first)
    second.update(question_id="q_2", question_number=2)
    calls = []

    def generated_item(question_id, question_number, *, bad=False):
        question, answer = valid_function_mc()
        question = deepcopy(question)
        answer = deepcopy(answer)
        question.update(id=question_id, number=question_number)
        answer.update(question_id=question_id, question_number=question_number)
        if bad:
            question["options"]["A"] = second["achievement"]
            answer["explanation"] = "Phù hợp với yêu cầu cần đạt nên đáp án A đúng."
        return question, answer

    def fake_run(batch, grade, failures):
        calls.append(([item["question_id"] for item in batch], deepcopy(failures)))
        if len(calls) == 1:
            q1, a1 = generated_item("q_1", 1)
            q2, a2 = generated_item("q_2", 2, bad=True)
            return {"questions": [q1, q2], "answer_key": [a1, a2], "rubric": []}
        q2, a2 = generated_item("q_2", 2)
        return {"questions": [q2], "answer_key": [a2], "rubric": []}

    monkeypatch.setattr(agent, "_run_gemini", fake_run)
    result = await agent._generate_validated_batch(
        [first, second], grade=8, batch_index=1, inherited_failures={}
    )

    assert calls[0][0] == ["q_1", "q_2"]
    assert calls[1][0] == ["q_2"]
    assert "learning_objective_copy" in calls[1][1]["q_2"]
    assert [item["id"] for item in result["questions"]] == ["q_1", "q_2"]


def test_persistence_gate_rejects_major_validation_errors():
    with pytest.raises(HTTPException) as exc_info:
        ExamService._require_persistable({"errors": ["Đáp án không hợp lệ"]})
    assert exc_info.value.status_code == 422


def test_missing_provider_question_shape_is_rejected_not_silently_saved():
    agent = QuestionAgent()
    item = spec("Nêu được chức năng của tim người.")

    normalized = agent._normalize_gemini_output(
        {"questions": [], "answer_key": [], "rubric": []},
        [item],
    )

    assert normalized["questions"][0]["metadata"]["scope_guard"]["status"] == "replaced"
    failures = agent._quality_issues(normalized, [item], grade=8)
    assert "generated_shape_replaced" in {issue.code for issue in failures["q_1"]}


@pytest.mark.asyncio
async def test_generation_groups_type_homogeneous_bounded_batches(monkeypatch):
    agent = QuestionAgent()
    agent.has_ai = True
    monkeypatch.setattr(settings, "AI_GENERATION_BATCH_SIZE", 4)
    seen = []

    async def fake_batch(batch, *, grade, batch_index, inherited_failures):
        seen.append((len(batch), {item["question_type"] for item in batch}))
        return {
            "questions": [
                {"id": item["question_id"], "number": item["question_number"]}
                for item in batch
            ],
            "answer_key": [
                {"question_id": item["question_id"], "question_number": item["question_number"]}
                for item in batch
            ],
            "rubric": [],
        }

    monkeypatch.setattr(agent, "_generate_validated_batch", fake_batch)
    items = []
    for index in range(1, 10):
        item = spec(
            "Nêu được chức năng của tim người.",
            question_type="multiple_choice" if index <= 5 else "true_false",
        )
        item.update(question_id=f"q_{index}", question_number=index)
        items.append(item)

    result = await agent.run(specification=items, grade=8)

    assert seen == [(4, {"multiple_choice"}), (1, {"multiple_choice"}), (4, {"true_false"})]
    assert [item["number"] for item in result["questions"]] == list(range(1, 10))


def test_independent_semantic_major_issue_is_a_hard_regeneration_reason():
    report = {
        "question_reports": [
            {
                "question_id": "q_3",
                "checks": {"solve_compare": {"status": "mismatch", "multiple_correct": False}},
                "issues": [
                    {
                        "severity": "major",
                        "type": "learning_objective_copy",
                    }
                ],
            }
        ]
    }

    assert VerificationAgent.hard_failure_reasons(report) == {
        "q_3": ["independent_answer_mismatch", "learning_objective_copy"]
    }


def test_unavailable_independent_reviewer_blocks_persistence_path():
    report = {
        "question_reports": [
            {
                "question_id": "q_4",
                "status": "not_verified",
                "checks": {"solve_compare": {"status": "skipped", "reason": "provider unavailable"}},
                "issues": [],
            }
        ]
    }

    assert VerificationAgent.hard_failure_reasons(
        report, require_independent=True
    ) == {
        "q_4": ["semantic_review_unavailable"]
    }


def local_formula_spec(*, grade, topic, objective):
    item = spec(objective, topic=topic, source_context="")
    item.pop("source_context", None)
    item.pop("source", None)
    return apply_local_sources([item], grade=grade)[0]


def calculation(formula_id, known_values, target, value, unit):
    return {
        "formula_id": formula_id,
        "known_values": known_values,
        "target_symbol": target,
        "calculation_steps": ["Tính bằng quan hệ đã kiểm soát."],
        "result": {"value": value, "unit": unit},
        "rounding_decimals": None,
    }


def test_local_curriculum_objective_drives_formula_allowlist():
    item = local_formula_spec(
        grade=7,
        topic="Tốc độ chuyển động",
        objective="Tính được tốc độ, quãng đường, thời gian.",
    )
    plan = build_generation_plan(item, grade=7)

    assert item["objective_id"] == "khtn7_obj_012"
    assert allowed_formula_ids(
        grade=7,
        spec=item,
        knowledge_target=plan.knowledge_target,
        source_context=plan.source_context,
    ) == ["SPEED"]
    assert capability_issues(
        "SPEED",
        grade=7,
        target_symbol="v",
        spec=item,
        knowledge_target=plan.knowledge_target,
        source_context=plan.source_context,
    ) == []


def test_formula_registry_rejects_wrong_grade_and_unsupported_local_objective():
    rag_item = spec(
        "Tính được tốc độ của vật.",
        topic="Tốc độ chuyển động",
        source_context="Tốc độ được tính từ quãng đường chia cho thời gian.",
    )
    codes = {
        code
        for code, _ in capability_issues(
            "SPEED",
            grade=8,
            target_symbol="v",
            spec=rag_item,
            knowledge_target="tốc độ của vật",
            source_context=rag_item["source_context"],
        )
    }
    assert "formula_grade_mismatch" in codes

    pressure_item = local_formula_spec(
        grade=8,
        topic="Khối lượng riêng và áp suất",
        objective="Trình bày được khái niệm áp suất và đơn vị đo áp suất.",
    )
    pressure_plan = build_generation_plan(pressure_item, grade=8)
    assert "PRESSURE" not in allowed_formula_ids(
        grade=8,
        spec=pressure_item,
        knowledge_target=pressure_plan.knowledge_target,
        source_context=pressure_plan.source_context,
    )


@pytest.mark.parametrize(
    ("payload", "expected", "unit"),
    [
        (
            calculation(
                "RELATIVE_MOLECULAR_MASS",
                [
                    {"symbol": "ar_1", "value": 1, "unit": "1"},
                    {"symbol": "count_1", "value": 2, "unit": "1"},
                    {"symbol": "ar_2", "value": 16, "unit": "1"},
                    {"symbol": "count_2", "value": 1, "unit": "1"},
                ],
                "mr", 18, "1",
            ),
            18, "1",
        ),
        (
            calculation(
                "GAS_RELATIVE_DENSITY_H2",
                [{"symbol": "molar_mass", "value": 44, "unit": "g/mol"}],
                "d_h2", 22, "1",
            ),
            22, "1",
        ),
        (
            calculation(
                "MOLAR_MASS_FROM_COMPOSITION",
                [
                    {"symbol": "ar_1", "value": 1, "unit": "1"},
                    {"symbol": "count_1", "value": 2, "unit": "1"},
                    {"symbol": "ar_2", "value": 16, "unit": "1"},
                    {"symbol": "count_2", "value": 1, "unit": "1"},
                ],
                "molar_mass", 18, "g/mol",
            ),
            18, "g/mol",
        ),
        (
            calculation(
                "MOLAR_GAS_VOLUME_STP",
                [{"symbol": "n", "value": 0.5, "unit": "mol"}],
                "v", 11.2, "L",
            ),
            11.2, "L",
        ),
        (
            calculation(
                "MECHANICAL_ENERGY",
                [
                    {"symbol": "kinetic_energy", "value": 20, "unit": "J"},
                    {"symbol": "potential_energy", "value": 30, "unit": "J"},
                ],
                "mechanical_energy", 50, "J",
            ),
            50, "J",
        ),
        (
            calculation(
                "ELECTRIC_POWER",
                [
                    {"symbol": "u", "value": 12, "unit": "V"},
                    {"symbol": "i", "value": 2, "unit": "A"},
                ],
                "p", 24, "W",
            ),
            24, "W",
        ),
        (
            calculation(
                "ELECTRIC_ENERGY",
                [
                    {"symbol": "p", "value": 2, "unit": "kW"},
                    {"symbol": "t", "value": 3, "unit": "h"},
                ],
                "e", 6, "kWh",
            ),
            6, "kWh",
        ),
        (
            calculation(
                "SERIES_RESISTANCE",
                [
                    {"symbol": "r_1", "value": 2, "unit": "ohm"},
                    {"symbol": "r_2", "value": 4, "unit": "ohm"},
                ],
                "r", 6, "ohm",
            ),
            6, "ohm",
        ),
        (
            calculation(
                "PARALLEL_RESISTANCE_TWO",
                [
                    {"symbol": "r_1", "value": 6, "unit": "ohm"},
                    {"symbol": "r_2", "value": 3, "unit": "ohm"},
                ],
                "r", 2, "ohm",
            ),
            2, "ohm",
        ),
    ],
)
def test_extended_curriculum_formula_solvers(payload, expected, unit):
    value, actual_unit, _ = solve_calculation(payload)
    assert float(value) == expected
    assert actual_unit == unit


@pytest.mark.parametrize(
    "payload",
    [
        calculation(
            "MOLAR_MASS_FROM_COMPOSITION",
            [
                {"symbol": "Ar(S)", "value": 32, "unit": ""},
                {"symbol": "n(S)", "value": 1, "unit": ""},
                {"symbol": "Ar(O)", "value": 16, "unit": ""},
                {"symbol": "n(O)", "value": 2, "unit": ""},
            ],
            "molar_mass", 64, "g/mol",
        ),
        calculation(
            "GAS_RELATIVE_DENSITY_H2",
            [{"symbol": "M(A)", "value": 28, "unit": "g/mol"}],
            "d_h2", 14, "",
        ),
    ],
)
def test_safe_solver_normalizes_conventional_chemistry_symbols(payload):
    value, _unit, _relationship = solve_calculation(payload)
    assert float(value) in {14, 64}


def test_every_advertised_formula_has_exactly_one_safe_solver():
    assert set(FORMULA_CAPABILITIES) == set(SOLVERS)
    assert set(FORMULA_CAPABILITIES) == set(
        get_args(GeneratedCalculation.model_fields["formula_id"].annotation)
    )


def test_electric_energy_equivalent_options_fail_single_choice():
    payload = calculation(
        "ELECTRIC_ENERGY",
        [
            {"symbol": "p", "value": 2, "unit": "kW"},
            {"symbol": "t", "value": 3, "unit": "h"},
        ],
        "e", 6, "kWh",
    )
    question = {
        "type": "multiple_choice",
        "options": {
            "A": "6 kWh",
            "B": "21600000 J",
            "C": "6000 J",
            "D": "0,6 kWh",
        },
        "correct_answer": "A",
    }
    issues = validate_calculation(payload, question, {"correct_answer": "A"})
    assert "numeric_correct_option_count" in {issue.code for issue in issues}


def test_question_prompt_exposes_only_formula_capabilities_for_that_objective():
    item = local_formula_spec(
        grade=7,
        topic="Tốc độ chuyển động",
        objective="Tính được tốc độ, quãng đường, thời gian.",
    )
    captured = {}

    class CaptureProvider:
        def generate_json(self, prompt, response_model=None):
            captured["prompt"] = prompt
            return {"questions": [], "answer_key": [], "rubric": []}

    agent = QuestionAgent()
    agent.gemini = CaptureProvider()
    agent._run_gemini([item], grade=7)

    capability_section = captured["prompt"].split("Capability công thức", 1)[1].split("Lý do batch", 1)[0]
    assert '"formula_id": "SPEED"' in capability_section
    assert '"known_value_symbol_contract"' in capability_section
    assert 's (quãng đường), t (thời gian), v (tốc độ)' in capability_section
    assert '"formula_id": "OHM"' not in capability_section


def test_application_level_definition_uses_application_reasoning():
    item = spec('Nêu được khái niệm nồng độ phần trăm.', topic='Dung dịch và nồng độ dung dịch', difficulty='van_dung')
    assert build_generation_plan(item, grade=8).reasoning_mode == 'application'


def test_missing_answer_placeholder_is_never_accepted_as_scientific_prose():
    item = spec('Nêu được khái niệm nhiệt lượng.', topic='Nhiệt', difficulty='nhan_biet')
    q = {'id': 'q_1', 'type': 'short_answer', 'content': 'Nhiệt lượng đo bằng đơn vị nào?', 'metadata': {}}
    answer = {'correct_answer': 'J', 'explanation': 'Đáp án dự kiến là J. Bản ghi cũ chưa lưu lời giải khoa học; cần tạo lại trước khi sử dụng.'}
    issues = validate_generated_item(question=q, answer=answer, rubric=None, spec=item, plan=build_generation_plan(item, grade=8))
    assert 'answer_content_missing' in {issue.code for issue in blocking_issues(issues)}


def test_preserved_shallow_answer_still_fails_scientific_validation():
    item = spec('Nêu được khái niệm nhiệt lượng.', topic='Nhiệt', difficulty='nhan_biet')
    q = {'id': 'q_1', 'type': 'short_answer', 'content': 'Nhiệt lượng đo bằng đơn vị nào?', 'metadata': {}}
    answer = {'correct_answer': 'J', 'explanation': 'Phương án này đúng.'}
    issues = validate_generated_item(question=q, answer=answer, rubric=None, spec=item, plan=build_generation_plan(item, grade=8))
    assert 'explanation_too_shallow' in {issue.code for issue in blocking_issues(issues)}
