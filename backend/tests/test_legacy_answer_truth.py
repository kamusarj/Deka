from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.services.exam.answer_content import normalize_answer
from app.services.exam.serializers import to_export_dict


@pytest.mark.parametrize("canonical", [None, "", "missing"])
def test_legacy_mc_preserves_stored_truth_when_question_omits_it(canonical):
    question = {"id": "q1", "number": 1, "type": "multiple_choice",
                "options": {"A": "Wrong", "B": "Right"}}
    if canonical != "missing":
        question["correct_answer"] = canonical
    answer = {"question_id": "q1", "correct_answer": "B"}
    original = deepcopy((question, answer))
    result = normalize_answer(answer, question, {})
    assert result["correct_answer"] == "B"
    assert "là B" in result["explanation"]
    assert "Đáp án dự kiến là B" in result["option_explanations"]["B"]
    assert (question, answer) == original


def test_legacy_tf_uses_matching_stored_truth_without_overriding_canonical_truth():
    question = {"id": "q1", "type": "true_false", "statements": [
        {"id": "a", "content": "True legacy statement"},
        {"id": "b", "content": "Canonical false", "is_true": False},
        {"id": "c", "content": "True legacy null", "is_true": None},
    ]}
    answer = {"answers": [
        {"statement_id": "c", "is_true": True},
        {"statement_id": "b", "is_true": True},
        {"statement_id": "a", "is_true": True},
    ]}
    original = deepcopy((question, answer))
    result = normalize_answer(answer, question, {})
    assert [item["is_true"] for item in result["answers"]] == [True, False, True]
    assert result["answers"][0]["explanation"].startswith("Đúng.")
    assert (question, answer) == original


def test_explicit_mc_question_truth_stays_authoritative():
    result = normalize_answer({"correct_answer": "B"}, {
        "id": "q1", "type": "multiple_choice", "correct_answer": "A",
        "options": {"A": "Right", "B": "Wrong"},
    }, {})
    assert result["correct_answer"] == "A"


def test_export_projection_preserves_legacy_truth_in_original_and_every_variant():
    exam = SimpleNamespace(
        id=161, owner_user_id=1, school_id=None, publication_status="verified",
        school="School", grade=8, subject="Science", exam_type="Test",
        duration_minutes=45, school_year="2026-2027", total_score=10,
        matrix=[], summary={}, specification=[], rubric=[], validation={},
        review_status={}, created_at=None, resource_package={"variant_count": 4},
        questions=[
            {"id": "q1", "number": 1, "type": "multiple_choice",
             "options": {"A": "Wrong", "B": "Right"}},
            {"id": "q2", "number": 2, "type": "true_false", "statements": [
                {"id": "a", "content": "True statement"},
                {"id": "b", "content": "False statement"},
            ]},
        ],
        answer_key=[
            {"question_id": "q1", "correct_answer": "B"},
            {"question_id": "q2", "answers": [
                {"statement_id": "a", "is_true": True},
                {"statement_id": "b", "is_true": False},
            ]},
        ],
    )
    original = deepcopy(vars(exam))
    exported = to_export_dict(exam)
    for paper in [exported, *exported["variants"]]:
        assert paper["answer_key"][0]["correct_answer"] == "B"
        tf_question = paper["questions"][1]
        truths = {item["statement_id"]: item["is_true"] for item in paper["answer_key"][1]["answers"]}
        for statement in tf_question["statements"]:
            assert truths[statement["id"]] is statement["content"].startswith("True")
    assert vars(exam) == original
