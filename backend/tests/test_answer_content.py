from app.services.exam.answer_content import normalize_answer


SPEC = {
    "question_id": "q_1",
    "question_number": 1,
    "question_type": "multiple_choice",
    "topic": "Tế bào",
    "achievement": "Nêu được tế bào là đơn vị cấu trúc cơ bản của cơ thể sống.",
    "rag_context": "Tế bào là đơn vị cấu trúc cơ bản của cơ thể sống.",
    "source": {
        "source_type": "rag_retrieval",
        "source_name": "SGK Sinh học 10.pdf",
        "source_page": 12,
        "source_section": "Bài 3 · Tế bào",
        "source_excerpt": "Tế bào là đơn vị cấu trúc cơ bản của cơ thể sống.",
        "doc_id": 7,
        "retrieved_chunk_id": "doc_7_4",
    },
}


def mc_question():
    return {
        "id": "q_1",
        "number": 1,
        "type": "multiple_choice",
        "content": "Đơn vị cấu trúc cơ bản của cơ thể sống là gì?",
        "options": {"A": "Tế bào", "B": "Mô", "C": "Cơ quan", "D": "Hệ cơ quan"},
        "correct_answer": "A",
        "source": SPEC["source"],
        "metadata": {"topic": "Tế bào"},
    }


def test_deterministic_answer_explains_every_option_and_attaches_exact_source():
    answer = normalize_answer(None, mc_question(), SPEC)

    assert answer["explanation"].startswith("Đáp án dự kiến đang lưu là A")
    assert "chưa có lời giải khoa học đủ chi tiết" in answer["explanation"]
    assert set(answer["option_explanations"]) == {"A", "B", "C", "D"}
    assert answer["citations"] == [{
        "source_type": "rag_retrieval",
        "source_name": "SGK Sinh học 10.pdf",
        "source_page": 12,
        "source_section": "Bài 3 · Tế bào",
        "excerpt": "Tế bào là đơn vị cấu trúc cơ bản của cơ thể sống.",
        "doc_id": 7,
        "retrieved_chunk_id": "doc_7_4",
        "verification_status": "verified",
        "verification_reason": "Đoạn trích khớp chính xác với chunk tài liệu đã được hệ thống truy xuất.",
        "verified_against": "retrieved_chunk",
    }]


def test_model_citation_is_discarded_in_favour_of_server_source():
    malicious = {
        "question_id": "q_1",
        "correct_answer": "A",
        "explanation": "A đúng vì tế bào là đơn vị cấu trúc cơ bản của cơ thể sống; các phương án còn lại là các cấp tổ chức lớn hơn.",
        "citations": [{"source_name": "Tài liệu AI tự bịa.pdf", "source_page": 999}],
    }

    answer = normalize_answer(malicious, mc_question(), SPEC)

    assert answer["citations"][0]["source_name"] == "SGK Sinh học 10.pdf"
    assert answer["citations"][0]["source_page"] == 12
    assert answer["citations"][0]["verification_status"] == "verified"


def test_mismatched_retrieved_excerpt_is_rejected_and_never_quoted():
    spec = {
        **SPEC,
        "source": {
            **SPEC["source"],
            "source_excerpt": "Đoạn trích đã bị thay đổi.",
        },
    }

    answer = normalize_answer(None, mc_question(), spec)
    citation = answer["citations"][0]

    assert citation["verification_status"] == "rejected"
    assert "excerpt" not in citation
    assert "không khớp" in citation["verification_reason"]


def test_local_curriculum_excerpt_is_verified_against_achievement():
    achievement = "Nêu được tế bào là đơn vị cấu trúc cơ bản của cơ thể sống."
    spec = {
        **SPEC,
        "rag_context": None,
        "achievement": achievement,
        "source": {
            "source_type": "local_json",
            "source_name": "khtn_grade_8.json",
            "source_section": "Chủ đề: Tế bào · Yêu cầu cần đạt",
            "source_excerpt": achievement,
        },
    }

    citation = normalize_answer(None, mc_question(), spec)["citations"][0]

    assert citation["verification_status"] == "verified"
    assert citation["verified_against"] == "curriculum_record"
    assert citation["excerpt"] == achievement


def test_legacy_question_source_is_unverified_and_not_quoted():
    legacy_spec = {key: value for key, value in SPEC.items() if key not in {"source", "rag_context"}}

    citation = normalize_answer(None, mc_question(), legacy_spec)["citations"][0]

    assert citation["verification_status"] == "unverified"
    assert "excerpt" not in citation


def test_true_false_preserves_prose_for_validation_and_authoritative_truth():
    question = {
        **mc_question(),
        "type": "true_false",
        "statements": [
            {"id": "s_1", "content": "Tế bào là đơn vị cấu trúc cơ bản.", "is_true": True},
            {"id": "s_2", "content": "Mô là đơn vị nhỏ nhất của sự sống.", "is_true": False},
        ],
    }
    supplied = {
        "answers": [
            {"statement_id": "s_1", "is_true": False, "explanation": "chung chung"},
            {"statement_id": "s_2", "is_true": True, "explanation": "chung chung"},
        ],
    }

    answer = normalize_answer(supplied, question, {**SPEC, "question_type": "true_false"})

    assert [item["is_true"] for item in answer["answers"]] == [True, False]
    # Normalization must not invent a longer explanation that masks shallow
    # input; the semantic validator is responsible for rejecting this prose.
    assert all(item["explanation"] == "chung chung" for item in answer["answers"])


def test_answer_without_stored_source_never_invents_a_citation():
    question = {**mc_question(), "source": None}
    answer = normalize_answer(None, question, {key: value for key, value in SPEC.items() if key != "source"})
    assert answer["citations"] == []


def test_concise_scientific_prose_survives_normalization_and_repeated_reads():
    for kind, supplied in [
        ('multiple_choice', {'explanation': 'Nhiệt lượng là năng lượng truyền do chênh lệch nhiệt độ, đo bằng J.'}),
        ('short_answer', {'correct_answer': '9 g', 'explanation': 'Khối lượng nước là m = n × M = 0,5 × 18 = 9 g.'}),
        ('essay', {'model_answer': 'Một mol chứa 6,02 × 10²³ hạt nên 0,5 mol chứa 3,01 × 10²³ hạt.'}),
    ]:
        q, spec = {**mc_question(), 'type': kind}, {**SPEC, 'question_type': kind}
        normalized = normalize_answer(supplied, q, spec)
        reread = normalize_answer(normalized, q, spec)
        for field in ('explanation', 'model_answer'):
            if field in supplied:
                assert normalized[field] == reread[field] == supplied[field]


def test_true_false_null_answers_get_explicit_missing_prose_without_crashing():
    q = {**mc_question(), 'type': 'true_false', 'statements': [
        {'id': 's1', 'content': 'Nhiệt lượng có đơn vị J.', 'is_true': True},
    ]}
    answer = normalize_answer({'answers': None}, q, {**SPEC, 'question_type': 'true_false'})
    assert answer['answers'][0]['statement_id'] == 's1'
    assert 'Bản ghi cũ chưa' in answer['answers'][0]['explanation']
