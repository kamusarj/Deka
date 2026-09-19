"""Unit coverage for the helpers extracted out of ExamService.

These run against plain objects — no database session, no AI provider — which
is the point of the extraction.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.exam import grounding, review, serializers, variants


def make_exam(**overrides):
    base = dict(
        id=7,
        questions=[],
        answer_key=[],
        resource_package={},
        school="THCS Nguyễn Du",
        grade=8,
        subject="Khoa học tự nhiên",
        exam_type="Giữa học kì I",
        duration_minutes=45,
        school_year="2025-2026",
        total_score=10,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ── variants ────────────────────────────────────────────────────────────────

def test_variant_count_defaults_when_unset():
    assert variants.variant_count(make_exam()) == variants.DEFAULT_VARIANT_COUNT


def test_variant_count_clamps_to_allowed_range():
    assert variants.variant_count(make_exam(resource_package={"variant_count": 0})) == 1
    assert (
        variants.variant_count(make_exam(resource_package={"variant_count": 999}))
        == variants.MAX_VARIANT_COUNT
    )


def test_variant_count_survives_a_non_numeric_value():
    assert (
        variants.variant_count(make_exam(resource_package={"variant_count": "bốn"}))
        == variants.DEFAULT_VARIANT_COUNT
    )


def test_variant_codes_start_at_101():
    assert variants.variant_codes(3) == ["101", "102", "103"]


def test_multiple_choice_shuffle_is_deterministic():
    questions = [{"id": f"q{i}", "type": "multiple_choice"} for i in range(6)]

    first = variants.ordered_multiple_choice_questions(questions, 7, "102", 1)
    second = variants.ordered_multiple_choice_questions(questions, 7, "102", 1)

    assert [q["id"] for q in first] == [q["id"] for q in second]


def test_different_variant_codes_produce_different_orders():
    questions = [{"id": f"q{i}", "type": "multiple_choice"} for i in range(6)]

    a = variants.ordered_multiple_choice_questions(questions, 7, "101", 0)
    b = variants.ordered_multiple_choice_questions(questions, 7, "102", 1)

    assert [q["id"] for q in a] != [q["id"] for q in b]


def test_single_question_is_left_alone():
    questions = [{"id": "q1", "type": "multiple_choice"}]
    assert variants.ordered_multiple_choice_questions(questions, 7, "103", 2) == questions


def test_build_variants_renumbers_and_prefixes_ids():
    exam = make_exam(
        resource_package={"variant_count": 2},
        questions=[
            {"id": "q1", "number": 1, "type": "multiple_choice", "content": "Câu 1"},
            {"id": "q2", "number": 2, "type": "short_answer", "content": "Câu 2"},
        ],
        answer_key=[
            {"question_id": "q1", "correct_answer": "A"},
            {"question_id": "q2", "correct_answer": "42"},
        ],
    )

    built = variants.build_variants(exam)

    assert [variant["code"] for variant in built] == ["101", "102"]
    for variant in built:
        code = variant["code"]
        assert [q["id"] for q in variant["questions"]] == [f"{code}_q1", f"{code}_q2"]
        assert [q["number"] for q in variant["questions"]] == [1, 2]
        assert [a["question_id"] for a in variant["answer_key"]] == [f"{code}_q1", f"{code}_q2"]
        assert [a["original_question_id"] for a in variant["answer_key"]] == ["q1", "q2"]


def test_build_variants_preserves_verified_calculation_content_and_answer():
    content = "Tính khối lượng mol của NaCl."
    explanation = "M = 23 + 35,5 = 58,5 g/mol."
    exam = make_exam(
        resource_package={"variant_count": 2},
        questions=[
            {
                "id": "q13",
                "number": 13,
                "type": "short_answer",
                "content": content,
                "metadata": {
                    "is_calculation": True,
                    "calculation_verified": True,
                },
            }
        ],
        answer_key=[
            {
                "question_id": "q13",
                "correct_answer": "58,5 g/mol",
                "explanation": explanation,
            }
        ],
    )

    built = variants.build_variants(exam)

    assert all(variant["questions"][0]["content"] == content for variant in built)
    assert all(
        variant["answer_key"][0]["explanation"] == explanation
        for variant in built
    )


def test_true_false_variation_rewrites_statement_ids_and_answers():
    question = {
        "id": "101_q1",
        "original_id": "q1",
        "type": "true_false",
        "content": "Phát biểu nào đúng?",
        "statements": [
            {"id": "s1", "content": "A đúng.", "is_true": True},
            {"id": "s2", "content": "B sai.", "is_true": False},
        ],
    }
    answer: dict = {}

    variants.vary_true_false_question(question, answer, "101", 0)

    assert question["content"] == "Phát biểu nào đúng?"
    assert [s["id"] for s in question["statements"]] == ["101_q1_s1", "101_q1_s2"]
    assert {a["statement_id"] for a in answer["answers"]} == {"101_q1_s1", "101_q1_s2"}
    # Truth values must survive the shuffle.
    assert sorted(a["is_true"] for a in answer["answers"]) == [False, True]


def test_true_false_variation_tolerates_a_question_with_no_statements():
    question = {"id": "101_q1", "type": "true_false", "content": "Trống"}
    answer: dict = {}

    variants.vary_true_false_question(question, answer, "101", 0)

    assert "answers" not in answer


def test_essay_variation_preserves_wording_answers_and_key_points():
    question = {
        "id": "101_q5",
        "type": "essay",
        "content": "Trình bày.",
        "sub_questions": [{"id": "old", "content": "Ý a"}],
    }
    answer = {"model_answer": "Đáp án mẫu.", "key_points": ["Ý chính"]}

    variants.vary_written_question(question, answer, "101", 0)

    assert question["sub_questions"][0]["id"] == "101_q5_sub1"
    assert question["content"] == "Trình bày."
    assert question["sub_questions"][0]["content"] == "Ý a"
    assert answer["model_answer"] == "Đáp án mẫu."
    assert answer["key_points"] == ["Ý chính"]


def test_essay_variation_tolerates_nullable_structured_output_collections():
    question = {
        "id": "101_q5",
        "type": "essay",
        "content": "Trình bày.",
        "sub_questions": None,
    }
    answer = {
        "model_answer": "Đáp án mẫu.",
        "key_points": None,
    }

    variants.vary_written_question(question, answer, "101", 0)

    assert question["sub_questions"] is None
    assert answer["key_points"] is None


# ── review ──────────────────────────────────────────────────────────────────

def test_reset_review_status_marks_everything_pending():
    status = review.reset_review_status([{"id": "q1"}, {"id": "q2"}])
    assert set(status) == {"q1", "q2"}
    assert all(entry["status"] == "pending" for entry in status.values())


def test_reset_review_status_handles_none():
    assert review.reset_review_status(None) == {}


def test_apply_review_ids_stamps_status_and_timestamp():
    status: dict = {}
    review.apply_review_ids(status, ["q1"], {"q1", "q2"}, status="accepted")

    assert status["q1"]["status"] == "accepted"
    assert status["q1"]["reviewed_at"]
    assert status["q1"]["reviewed_by"] == "teacher"


def test_apply_review_ids_preserves_a_known_reviewer():
    status = {"q1": {"reviewed_by": "cô Lan"}}
    review.apply_review_ids(status, ["q1"], {"q1"}, status="rejected")
    assert status["q1"]["reviewed_by"] == "cô Lan"


def test_apply_review_ids_rejects_an_unknown_question():
    with pytest.raises(HTTPException) as excinfo:
        review.apply_review_ids({}, ["ghost"], {"q1"}, status="accepted")
    assert excinfo.value.status_code == 400


def test_replace_by_id_swaps_matches_and_appends_new_items():
    current = [{"id": "a", "v": 1}, {"id": "b", "v": 2}]
    replacements = [{"id": "b", "v": 20}, {"id": "c", "v": 30}]

    result = review.replace_by_id(current, replacements, "id")

    assert result == [{"id": "a", "v": 1}, {"id": "b", "v": 20}, {"id": "c", "v": 30}]


def test_curriculum_from_text_reads_period_counts():
    items = review.curriculum_from_text(
        "- Chủ đề 1: Hệ tuần hoàn (6 tiết)\n\n- Chủ đề 2: Hô hấp\n"
    )

    assert [item.topic for item in items] == ["Chủ đề 1: Hệ tuần hoàn", "Chủ đề 2: Hô hấp"]
    assert [item.periods for item in items] == [6, 1]


# ── grounding ───────────────────────────────────────────────────────────────

class FakeRetriever:
    def __init__(self, chunks, hits):
        self.chunks = chunks
        self._hits = hits

    def retrieve(self, query, k=1):
        return self._hits


class FakeKnowledgeBase:
    def __init__(self, retriever):
        self._retriever = retriever

    def build_retriever(self, **_kwargs):
        return self._retriever


def test_grounding_is_a_no_op_without_documents():
    spec = [{"topic": "Hệ tuần hoàn"}]
    assert grounding.apply_rag_sources(None, spec, document_ids=[]) is spec


def test_grounding_is_a_no_op_when_the_index_is_empty():
    spec = [{"topic": "Hệ tuần hoàn"}]
    kb = FakeKnowledgeBase(FakeRetriever(chunks=[], hits=[]))

    assert grounding.apply_rag_sources(kb, spec, document_ids=[1]) is spec


def test_grounding_tags_a_matching_spec_with_its_source():
    hit = {
        "score": 0.87654,
        "chunk": {
            "id": "c1",
            "text": "Tim có bốn ngăn.",
            "metadata": {
                "source_name": "SGK KHTN 8",
                "doc_id": 3,
                "source_page": 21,
                "source_section": "Bài 5",
            },
        },
    }
    kb = FakeKnowledgeBase(FakeRetriever(chunks=["c1"], hits=[hit]))

    enriched = grounding.apply_rag_sources(
        kb, [{"topic": "Hệ tuần hoàn"}], document_ids=[3]
    )

    source = enriched[0]["source"]
    assert enriched[0]["rag_context"] == "Tim có bốn ngăn."
    assert source["source_type"] == "rag_retrieval"
    assert source["source_name"] == "SGK KHTN 8"
    assert source["doc_id"] == 3
    assert source["retrieved_chunk_id"] == "c1"
    assert source["confidence_score"] == 0.8765
    assert source["source_page"] == 21
    assert source["source_section"] == "Bài 5"
    assert source["source_excerpt"] == "Tim có bốn ngăn."


def test_local_grounding_names_curriculum_file_and_exact_scope():
    enriched = grounding.apply_local_sources(
        [{"topic": "Hệ tuần hoàn", "achievement": "Mô tả được cấu tạo tim."}],
        grade=8,
    )

    source = enriched[0]["source"]
    assert source["source_name"] == "khtn_grade_8.json"
    assert source["source_section"] == "Chủ đề: Hệ tuần hoàn · Yêu cầu cần đạt"
    assert source["source_excerpt"] == "Mô tả được cấu tạo tim."


def test_local_grounding_keeps_curriculum_scope_separate_from_scientific_source():
    enriched = grounding.apply_local_sources(
        [{
            "topic": "Hệ tuần hoàn ở người",
            "achievement": "Mô tả được cấu tạo và chức năng của tim người.",
        }],
        grade=8,
    )[0]

    assert enriched["topic_id"] == "khtn8_topic_08"
    assert "hệ tuần hoàn" in enriched["source_context"].lower()
    assert enriched["source"]["source_excerpt"] == enriched["achievement"]
    assert enriched["source"]["source_type"] == "local_json"


def test_grounding_leaves_an_unmatched_spec_untouched():
    kb = FakeKnowledgeBase(FakeRetriever(chunks=["c1"], hits=[]))

    enriched = grounding.apply_rag_sources(
        kb, [{"topic": "Không khớp"}], document_ids=[3]
    )

    assert enriched == [{"topic": "Không khớp"}]


def test_serializer_preserves_supplied_answer_without_rewriting_storage():
    question = {
        "id": "q1",
        "number": 1,
        "type": "multiple_choice",
        "options": {"A": "Tim có bốn ngăn", "B": "Hai ngăn", "C": "Ba ngăn", "D": "Năm ngăn"},
        "correct_answer": "A",
        "source": {"source_type": "local_json", "source_name": "Local curriculum seed data"},
        "metadata": {"topic": "Tim"},
    }
    stored_answer = {"question_id": "q1", "explanation": "Phương án A phù hợp."}
    specification = [{
        "question_id": "q1",
        "question_number": 1,
        "question_type": "multiple_choice",
        "topic": "Tim",
        "achievement": "Mô tả được cấu tạo tim người gồm bốn ngăn.",
    }]

    rendered = serializers.normalized_answer_key([question], [stored_answer], specification)[0]

    assert rendered["explanation"] == stored_answer["explanation"]
    assert "Bản ghi" not in rendered["explanation"]
    assert set(rendered["option_explanations"]) == {"A", "B", "C", "D"}
    assert rendered["citations"][0]["verification_status"] == "unverified"
    assert "excerpt" not in rendered["citations"][0]
    assert stored_answer == {"question_id": "q1", "explanation": "Phương án A phù hợp."}
