import asyncio
import time

import pytest

from app.agents.question_agent import QuestionAgent
from app.core.config import settings
from app.schemas.ai_outputs import QuestionGenerationOutput


@pytest.mark.asyncio
async def test_question_agent_fallback_distributes_multiple_choice_answers():
    agent = QuestionAgent()
    agent.has_ai = False
    specification = [
        {
            "question_id": f"q_{index}",
            "question_number": index,
            "question_type": "multiple_choice",
            "difficulty": "thong_hieu",
            "score": 0.25,
            "topic": f"Tế bào {index}",
            "lesson": f"Bài {index}",
            "knowledge_unit": f"Kiến thức {index}",
            "achievement": f"Nêu được khái niệm tế bào {index}.",
            "bloom_level": "understand",
        }
        for index in range(1, 5)
    ]

    result = await agent.run(specification=specification)

    assert [answer["correct_answer"] for answer in result["answer_key"]] == ["A", "B", "C", "D"]
    for question, answer in zip(result["questions"], result["answer_key"], strict=True):
        assert "Nội dung nào sau đây" not in question["content"]
        assert "ở câu" not in question["content"]
        assert "Nêu được" not in question["options"][answer["correct_answer"]]
        assert "khái niệm tế bào" in question["options"][answer["correct_answer"]]


@pytest.mark.asyncio
async def test_question_agent_makes_same_topic_questions_distinct():
    """Nhiều câu cùng một chủ đề và dạng câu phải có nội dung khác nhau."""
    agent = QuestionAgent()
    agent.has_ai = False

    def spec(index, qtype):
        return {
            "question_id": f"q_{index}",
            "question_number": index,
            "question_type": qtype,
            "difficulty": "thong_hieu",
            "score": 0.25 if qtype == "multiple_choice" else 0.5,
            "topic": "Phản ứng hóa học",
            "lesson": "Phản ứng hóa học",
            "knowledge_unit": "Phản ứng hóa học",
            "achievement": "Trình bày được khái niệm phản ứng hóa học.",
            "bloom_level": "understand",
        }

    specification = [
        spec(1, "multiple_choice"),
        spec(2, "multiple_choice"),
        spec(3, "multiple_choice"),
        spec(4, "multiple_choice"),
        spec(5, "multiple_choice"),
        spec(6, "multiple_choice"),
        spec(7, "multiple_choice"),
        spec(8, "multiple_choice"),
        spec(9, "true_false"),
        spec(10, "true_false"),
    ]

    result = await agent.run(specification=specification)
    questions = result["questions"]

    contents = [q["content"].strip().lower() for q in questions]
    assert len(set(contents)) == len(contents), "Câu hỏi cùng chủ đề bị trùng nội dung"

    # Phương án trắc nghiệm của các câu cùng chủ đề cũng phải khác nhau.
    mc_option_sets = [
        tuple(sorted(q["options"].values()))
        for q in questions
        if q["type"] == "multiple_choice"
    ]
    assert len(set(mc_option_sets)) == len(mc_option_sets)

    # Phát biểu đúng/sai của các câu cùng chủ đề cũng phải khác nhau.
    tf_statement_sets = [
        tuple(s["content"] for s in q["statements"])
        for q in questions
        if q["type"] == "true_false"
    ]
    assert len(set(tf_statement_sets)) == len(tf_statement_sets)


def test_scope_guard_replaces_unrelated_ai_question():
    agent = QuestionAgent()
    spec = {
        "question_id": "q_1",
        "question_number": 1,
        "question_type": "multiple_choice",
        "difficulty": "nhan_biet",
        "score": 0.25,
        "topic": "Hệ tuần hoàn",
        "lesson": "Cấu tạo tim",
        "knowledge_unit": "Tim người",
        "achievement": "Mô tả được cấu tạo tim người.",
        "bloom_level": "remember",
    }
    generated = {
        "questions": [{
            "id": "q_1",
            "content": "Thủ đô của Pháp là thành phố nào?",
            "options": {"A": "Paris", "B": "Rome", "C": "Hà Nội", "D": "Tokyo"},
        }],
        "answer_key": [{"question_id": "q_1", "correct_answer": "A"}],
        "rubric": [],
    }

    result = agent._normalize_gemini_output(generated, [spec])
    question = result["questions"][0]

    assert question["metadata"]["scope_guard"]["status"] == "replaced"
    assert "Hệ tuần hoàn" in question["content"]
    assert "Pháp" not in question["content"]


def test_normalize_discards_model_authored_source():
    agent = QuestionAgent()
    trusted_source = {
        "source_type": "local_json",
        "source_name": "khtn_grade_8.json",
        "source_excerpt": "Mô tả được cấu tạo tim người.",
    }
    spec = {
        "question_id": "q_1",
        "question_number": 1,
        "question_type": "multiple_choice",
        "difficulty": "nhan_biet",
        "score": 0.25,
        "topic": "Hệ tuần hoàn",
        "lesson": "Cấu tạo tim",
        "knowledge_unit": "Tim người",
        "achievement": "Mô tả được cấu tạo tim người.",
        "bloom_level": "remember",
        "source": trusted_source,
    }
    generated = {
        "questions": [{
            "id": "q_1",
            "content": "Tim người có bốn ngăn và thuộc hệ tuần hoàn.",
            "options": {"A": "Bốn ngăn", "B": "Hai ngăn", "C": "Ba ngăn", "D": "Năm ngăn"},
            "source": {"source_name": "Tài liệu AI tự bịa.pdf", "source_page": 999},
        }],
        "answer_key": [{"question_id": "q_1", "correct_answer": "A"}],
        "rubric": [],
    }

    question = agent._normalize_gemini_output(generated, [spec])["questions"][0]

    assert question["source"] == trusted_source


def test_question_generation_passes_strict_output_contract():
    agent = QuestionAgent()
    agent.gemini.generate_json = lambda prompt, **kwargs: (
        setattr(agent, "received_prompt", prompt)
        or setattr(agent, "received_response_model", kwargs.get("response_model"))
        or {"questions": [], "answer_key": [], "rubric": []}
    )

    agent._run_gemini([])

    assert agent.received_response_model is QuestionGenerationOutput
    assert "tự đủ ngữ cảnh" in agent.received_prompt


MC_SPEC = {
    "question_id": "q_1",
    "question_number": 1,
    "question_type": "multiple_choice",
    "difficulty": "nhan_biet",
    "score": 0.25,
    "topic": "Tế bào",
    "lesson": "Tế bào",
    "knowledge_unit": "Tế bào",
    "achievement": "Nêu được khái niệm tế bào.",
    "bloom_level": "remember",
}

TF_SPEC = {
    **MC_SPEC,
    "question_type": "true_false",
    "score": 0.5,
}


def _mc_result(generated, spec=None):
    agent = QuestionAgent()
    result = agent._normalize_gemini_output(generated, [dict(spec or MC_SPEC)])
    return result["questions"][0], result["answer_key"][0]


def test_normalize_mc_missing_options_replaces_whole_pair():
    """AI trả answer_key nhưng thiếu options: không được giữ đáp án trỏ vào
    phương án nhiễu của bộ fallback."""
    question, answer = _mc_result({
        "questions": [{"id": "q_1", "content": "Trình bày khái niệm tế bào và cấu tạo tế bào."}],
        "answer_key": [{"question_id": "q_1", "correct_answer": "D"}],
        "rubric": [],
    })
    assert len(question["options"]) == 4
    assert "Nêu được" not in question["options"][question["correct_answer"]]
    assert "khái niệm tế bào" in question["options"][question["correct_answer"]]
    assert answer["correct_answer"] == question["correct_answer"]


def test_normalize_mc_invalid_answer_label_replaces_whole_pair():
    """AI có options nhưng đáp án trỏ nhãn không tồn tại: thay cả cặp."""
    question, answer = _mc_result({
        "questions": [{
            "id": "q_1",
            "content": "Trình bày khái niệm tế bào và cấu tạo tế bào.",
            "options": {"A": "Tế bào là đơn vị cấu tạo", "B": "Sai 1", "C": "Sai 2", "D": "Sai 3"},
        }],
        "answer_key": [{"question_id": "q_1", "correct_answer": "Z"}],
        "rubric": [],
    })
    assert question["correct_answer"] in question["options"]
    assert "Nêu được" not in question["options"][question["correct_answer"]]
    assert "khái niệm tế bào" in question["options"][question["correct_answer"]]
    assert answer["correct_answer"] == question["correct_answer"]


def test_normalize_mc_valid_ai_pair_is_kept():
    """Cặp options + đáp án hợp lệ của AI phải được giữ nguyên (case-insensitive)."""
    ai_options = {"A": "Sai 1", "B": "Tế bào là đơn vị cấu tạo của cơ thể", "C": "Sai 2", "D": "Sai 3"}
    question, answer = _mc_result({
        "questions": [{
            "id": "q_1",
            "content": "Trình bày khái niệm tế bào và cấu tạo tế bào.",
            "options": ai_options,
        }],
        "answer_key": [{"question_id": "q_1", "correct_answer": "b"}],
        "rubric": [],
    })
    assert question["options"] == ai_options
    assert question["correct_answer"] == "B"
    assert answer["correct_answer"] == "B"


def test_normalize_removes_ai_style_labels_from_question_text():
    ai_options = {
        "A": "[Nhận biết] Sai 1",
        "B": "Nội dung: Tế bào là đơn vị cấu tạo của cơ thể",
        "C": "Sai 2",
        "D": "Sai 3",
    }
    question, _answer = _mc_result({
        "questions": [{
            "id": "q_1",
            "content": "[Nhận biết] Câu hỏi: Trình bày khái niệm tế bào.",
            "options": ai_options,
        }],
        "answer_key": [{"question_id": "q_1", "correct_answer": "B"}],
        "rubric": [],
    })

    assert question["content"] == "Trình bày khái niệm tế bào."
    assert question["options"]["A"] == "Sai 1"
    assert question["options"]["B"] == "Tế bào là đơn vị cấu tạo của cơ thể"


def test_fallback_does_not_expose_regeneration_instruction():
    agent = QuestionAgent()
    question = agent._question({**MC_SPEC, "variant_note": "đổi số liệu và cách hỏi"})

    assert "Phiên bản tạo lại" not in question["content"]
    assert "đổi số liệu" not in question["content"]


def test_fallback_normalizes_terminal_punctuation():
    agent = QuestionAgent()
    question = agent._question(MC_SPEC)

    assert ".." not in question["content"]
    assert question["content"].endswith((".", "?"))


def test_normalize_true_false_answer_follows_kept_statements():
    """Cắt statements còn 4 thì answer_key phải khớp đúng các statement còn lại."""
    statements = [
        {"id": f"s_1_{index}", "content": f"Phát biểu số {index} về tế bào.", "is_true": index % 2 == 0}
        for index in range(1, 6)  # AI trả 5 phát biểu
    ]
    question, answer = _mc_result({
        "questions": [{
            "id": "q_1",
            "content": "Xét tính đúng/sai các phát biểu về tế bào.",
            "type": "true_false",
            "statements": statements,
        }],
        "answer_key": [{
            "question_id": "q_1",
            "type": "true_false",
            "answers": [
                {"statement_id": statement["id"], "is_true": statement["is_true"]}
                for statement in statements  # đáp án AI tham chiếu cả 5
            ],
        }],
        "rubric": [],
    }, spec=TF_SPEC)
    kept_ids = [statement["id"] for statement in question["statements"]]
    assert len(kept_ids) == 4
    assert [item["statement_id"] for item in answer["answers"]] == kept_ids
    assert answer["answers"][0]["is_true"] == question["statements"][0]["is_true"]


@pytest.mark.parametrize(
    "statements",
    [
        [
            {"id": "ai_1", "content": "Phát biểu một về tế bào.", "is_true": True},
            {"id": "ai_2", "content": "Phát biểu hai về tế bào.", "is_true": False},
        ],
        [
            {"id": "ai_1", "content": "Phát biểu một về tế bào.", "is_true": True},
            {"id": "ai_2", "content": "Phát biểu hai về tế bào.", "is_true": False},
            {"id": "ai_3", "content": "", "is_true": True},
            {"id": "ai_4", "content": "Phát biểu bốn về tế bào."},
        ],
    ],
)
def test_normalize_true_false_replaces_incomplete_or_malformed_statements(statements):
    question, answer = _mc_result({
        "questions": [{
            "id": "q_1",
            "content": "Xét tính đúng sai của các phát biểu về tế bào.",
            "type": "true_false",
            "statements": statements,
        }],
        "answer_key": [{
            "question_id": "q_1",
            "type": "true_false",
            "answers": [
                {
                    "statement_id": statement.get("id"),
                    "is_true": statement.get("is_true"),
                }
                for statement in statements
            ],
        }],
        "rubric": [],
    }, spec=TF_SPEC)

    assert len(question["statements"]) == 4
    assert all(
        statement.get("id")
        and statement.get("content")
        and isinstance(statement.get("is_true"), bool)
        for statement in question["statements"]
    )
    assert [item["statement_id"] for item in answer["answers"]] == [
        statement["id"] for statement in question["statements"]
    ]


@pytest.mark.asyncio
async def test_question_agent_ai_timeout_fails_closed_without_blocking_loop(monkeypatch):
    """A provider timeout must not stall FastAPI or silently save fixture content."""
    agent = QuestionAgent()
    agent.has_ai = True
    monkeypatch.setattr(settings, "AI_FAILOVER_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(agent, "_run_gemini", lambda _specification, _grade, _failures: time.sleep(0.05))
    specification = [{
        "question_id": "q_1", "question_number": 1, "question_type": "multiple_choice",
        "difficulty": "nhan_biet", "score": 0.25, "topic": "Tế bào", "lesson": "Tế bào",
        "knowledge_unit": "Tế bào", "achievement": "Nêu được khái niệm tế bào.",
        "bloom_level": "remember",
    }]

    heartbeat = asyncio.create_task(asyncio.sleep(0))
    with pytest.raises(asyncio.TimeoutError):
        await agent.run(specification=specification)
    await heartbeat

    assert heartbeat.done()
