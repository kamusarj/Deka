"""Deterministic exam-variant (mã đề) generation.

Every variant is derived from the stored exam with a seeded RNG, so the same
exam always produces the same variants — teachers can re-download a paper and
get exactly what they printed.
"""

from __future__ import annotations

import random
import re
from copy import deepcopy

DEFAULT_VARIANT_COUNT = 4
MAX_VARIANT_COUNT = 30

def variant_count(exam) -> int:
    """How many variants this exam asks for, clamped to a sane range."""
    resource_package = exam.resource_package or {}
    raw_count = resource_package.get("variant_count", DEFAULT_VARIANT_COUNT)
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        count = DEFAULT_VARIANT_COUNT
    return max(1, min(MAX_VARIANT_COUNT, count))


def variant_codes(count: int) -> list[str]:
    return [str(101 + index) for index in range(count)]


def build_variants(exam) -> list[dict]:
    answer_by_id = {
        answer.get("question_id"): answer
        for answer in (exam.answer_key or [])
        if answer.get("question_id")
    }
    codes = variant_codes(variant_count(exam))
    return [
        build_variant(exam, code, index, answer_by_id)
        for index, code in enumerate(codes)
    ]


def build_variant(exam, code: str, code_index: int, answer_by_id: dict) -> dict:
    source_questions = [deepcopy(question) for question in (exam.questions or [])]
    multiple_choice_questions = [
        question for question in source_questions
        if question.get("type") == "multiple_choice"
    ]
    shuffled_multiple_choice = ordered_multiple_choice_questions(
        multiple_choice_questions,
        exam.id,
        code,
        code_index,
    )
    multiple_choice_index = 0

    variant_questions = []
    variant_answers = []
    for question_number, source_question in enumerate(source_questions, start=1):
        if source_question.get("type") == "multiple_choice":
            question = deepcopy(shuffled_multiple_choice[multiple_choice_index])
            multiple_choice_index += 1
        else:
            question = deepcopy(source_question)

        original_id = question.get("id")
        original_number = question.get("number")
        variant_id = f"{code}_{original_id}"
        answer = deepcopy(answer_by_id.get(original_id, {}))

        question["original_id"] = original_id
        question["original_number"] = original_number
        question["id"] = variant_id
        question["number"] = question_number

        answer["original_question_id"] = original_id
        answer["question_id"] = variant_id
        answer["question_number"] = question_number
        answer["type"] = question.get("type", answer.get("type"))

        if question.get("type") == "multiple_choice":
            vary_multiple_choice_options(question, answer, exam.id, code)
        elif question.get("type") == "true_false":
            vary_true_false_question(question, answer, code, code_index)
        elif (
            question.get("type") in ("short_answer", "essay")
            and not (question.get("metadata") or {}).get("is_calculation")
        ):
            vary_written_question(question, answer, code, code_index)

        variant_questions.append(question)
        variant_answers.append(answer)

    return {
        "code": code,
        "questions": variant_questions,
        "answer_key": variant_answers,
    }


def ordered_multiple_choice_questions(
    questions: list[dict],
    exam_id: int | None,
    code: str,
    code_index: int,
) -> list[dict]:
    ordered = [deepcopy(question) for question in questions]
    if len(ordered) <= 1:
        return ordered
    rng = random.Random(f"exam:{exam_id}:variant:{code}:multiple-choice")
    rng.shuffle(ordered)
    if code_index:
        shift = code_index % len(ordered)
        ordered = ordered[shift:] + ordered[:shift]
    return ordered


def _remap_option_references(text: str, mapping: dict[str, str]) -> str:
    # Explicit answer-label references only: do not rename physical symbols A/B.
    return re.sub(r"(?i)(phương án|đáp án|lựa chọn|option|answer)(\s+)([ABCD])\b",
                  lambda m: m[1] + m[2] + mapping[m[3].upper()], str(text))


def vary_multiple_choice_options(question, answer, exam_id, code):
    options = question.get("options") or {}
    if not isinstance(options, dict) or set(options) != set("ABCD"):
        return
    # Legacy options such as 'A và B đều đúng' are position-dependent. Preserve
    # their order; new generation already discourages this construction.
    if any(re.search(r"\b[ABCD]\b", str(value)) for value in options.values()):
        return
    labels = list("ABCD")
    order = labels.copy()
    random.Random(f"exam:{exam_id}:variant:{code}:question:{question.get('original_id')}:options").shuffle(order)
    mapping = {old: new for new, old in zip(labels, order)}
    question["options"] = {new: options[old] for new, old in zip(labels, order)}
    correct = question.get("correct_answer") or answer.get("correct_answer")
    if correct in mapping:
        question["correct_answer"] = answer["correct_answer"] = mapping[correct]
    for payload in (question, answer):
        explanations = payload.get("option_explanations")
        if isinstance(explanations, dict):
            payload["option_explanations"] = {mapping.get(old, old): _remap_option_references(value, mapping) for old, value in explanations.items()}
        if payload.get("explanation"):
            payload["explanation"] = _remap_option_references(payload["explanation"], mapping)


def vary_true_false_question(question: dict, answer: dict, code: str, code_index: int) -> None:
    statements = [
        deepcopy(statement) for statement in (question.get("statements") or [])
    ]
    if not statements:
        return

    statement_rng = random.Random(f"variant:{code}:question:{question.get('original_id')}:statements")
    statement_rng.shuffle(statements)
    answers_by_id = {item.get("statement_id"): item for item in answer.get("answers", [])}
    reordered_answers = []
    for index, statement in enumerate(statements, start=1):
        statement_answer = deepcopy(answers_by_id.get(statement.get("id"), {}))
        statement["id"] = f"{question['id']}_s{index}"
        statement_answer["statement_id"] = statement["id"]
        statement_answer.setdefault("is_true", statement.get("is_true", False))
        statement_answer.setdefault("explanation", "")
        reordered_answers.append(statement_answer)
    question["statements"] = statements

    answer["answers"] = reordered_answers


def vary_written_question(question: dict, answer: dict, code: str, code_index: int) -> None:
    # Codes identify a paper, never introduce new scientific requirements.
    for index, sub_question in enumerate(question.get("sub_questions") or [], start=1):
        sub_question["id"] = f"{question['id']}_sub{index}"
