"""Build teacher-facing answer detail and trusted source evidence.

The model may help write pedagogical prose, but it is never authoritative for
document names, page numbers, section locators, or quotations. Those values are
derived from the specification/question source controlled by the application.
"""

from __future__ import annotations

from copy import deepcopy
import re


VERIFIED = "verified"
UNVERIFIED = "unverified"
REJECTED = "rejected"


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _scope_text(spec: dict) -> str:
    return _clean(
        spec.get("rag_context")
        or spec.get("source_context")
        or spec.get("knowledge_unit")
        or spec.get("topic")
        or spec.get("achievement")
    )


def _verify_source(source: dict, spec: dict, *, controlled: bool) -> tuple[str, str, str | None]:
    """Verify a locator against the exact server-owned grounding payload.

    This is intentionally deterministic. An LLM must never be the authority
    deciding whether its own quotation is genuine.
    """
    if not controlled:
        return (
            UNVERIFIED,
            "Bản ghi này không còn ngữ cảnh nguồn do hệ thống lưu để đối chiếu.",
            None,
        )

    source_type = _clean(source.get("source_type"))
    excerpt = _clean(source.get("source_excerpt"))
    if source_type == "rag_retrieval":
        expected = _clean(spec.get("rag_context"))
        has_locator = all(
            (
                _clean(source.get("source_name")),
                source.get("doc_id") is not None,
                _clean(source.get("retrieved_chunk_id")),
            )
        )
        if not expected or not excerpt or not has_locator:
            return (
                UNVERIFIED,
                "Thiếu đoạn truy xuất hoặc định danh tài liệu/chunk để kiểm chứng.",
                None,
            )
        if excerpt == expected:
            return (
                VERIFIED,
                "Đoạn trích khớp chính xác với chunk tài liệu đã được hệ thống truy xuất.",
                "retrieved_chunk",
            )
        return (
            REJECTED,
            "Đoạn trích không khớp chunk tài liệu đã được hệ thống truy xuất.",
            None,
        )

    if source_type == "local_json":
        expected = _clean(spec.get("achievement"))
        if not expected or not excerpt or not _clean(source.get("source_name")):
            return (
                UNVERIFIED,
                "Thiếu yêu cầu cần đạt hoặc đoạn trích chương trình để kiểm chứng.",
                None,
            )
        if excerpt == expected:
            return (
                VERIFIED,
                "Đoạn trích khớp chính xác với yêu cầu cần đạt trong dữ liệu chương trình.",
                "curriculum_record",
            )
        return (
            REJECTED,
            "Đoạn trích không khớp yêu cầu cần đạt trong dữ liệu chương trình.",
            None,
        )

    return (
        UNVERIFIED,
        "Loại nguồn này chưa có quy tắc kiểm chứng tự động.",
        None,
    )


def _source_citation(question: dict, spec: dict) -> dict | None:
    # A specification source is server-owned. The question fallback exists only
    # for historical records and is never promoted to verified evidence.
    controlled_source = spec.get("source") if isinstance(spec.get("source"), dict) else None
    source = controlled_source or question.get("source") or {}
    source_name = _clean(source.get("source_name"))
    if not source_name:
        return None

    status, reason, verified_against = _verify_source(
        source,
        spec,
        controlled=controlled_source is not None,
    )
    excerpt = _clean(source.get("source_excerpt")) if status == VERIFIED else ""
    topic = _clean(spec.get("topic") or (question.get("metadata") or {}).get("topic"))
    section = _clean(source.get("source_section"))
    if not section and topic:
        section = f"Chủ đề: {topic} · Yêu cầu cần đạt"

    citation = {
        "source_type": source.get("source_type") or "unknown",
        "source_name": source_name,
        "source_page": source.get("source_page"),
        "source_section": section or None,
        "excerpt": excerpt or None,
        "doc_id": source.get("doc_id"),
        "retrieved_chunk_id": source.get("retrieved_chunk_id"),
        "verification_status": status,
        "verification_reason": reason,
        "verified_against": verified_against,
    }
    return {key: value for key, value in citation.items() if value is not None}


def _mc_option_explanations(question: dict, correct_answer: str, scope: str) -> dict[str, str]:
    explanations: dict[str, str] = {}
    for label, raw_option in (question.get("options") or {}).items():
        option = _clean(raw_option)
        if str(label).upper() == correct_answer.upper():
            explanations[label] = (
                f"Đáp án dự kiến là {label}: “{option}”. Bản ghi này chưa có lời giải khoa học "
                "đủ chi tiết từ bộ sinh; cần tạo lại đáp án trước khi sử dụng."
            )
        else:
            explanations[label] = (
                f"Không chọn {label}: “{option}”. Bản ghi này chưa lưu lý do khoa học cụ thể; "
                "không nên sử dụng phương án cho tới khi đáp án được tạo lại."
            )
    return explanations


def _fallback_answer(question: dict, spec: dict) -> dict:
    question_id = question.get("id", spec.get("question_id", ""))
    question_number = question.get("number", spec.get("question_number", 0))
    question_type = question.get("type", spec.get("question_type", ""))
    scope = _scope_text(spec) or "nội dung kiến thức đã được xác định trong bản đặc tả"
    topic = _clean(spec.get("topic") or (question.get("metadata") or {}).get("topic"))
    base = {
        "question_id": question_id,
        "question_number": question_number,
        "type": question_type,
    }

    if question_type == "multiple_choice":
        correct = _clean(question.get("correct_answer") or "A").upper()
        option = _clean((question.get("options") or {}).get(correct))
        return {
            **base,
            "correct_answer": correct,
            "explanation": (
                f"Đáp án dự kiến đang lưu là {correct}: “{option}”. Hệ thống chưa có lời giải "
                "khoa học đủ chi tiết cho bản ghi này; hãy tạo lại đáp án để có cơ chế, dữ liệu "
                "hoặc phép tính chứng minh và lý do loại từng phương án."
            ),
            "option_explanations": _mc_option_explanations(question, correct, scope),
        }

    if question_type == "true_false":
        answers = []
        for statement in question.get("statements") or []:
            is_true = bool(statement.get("is_true"))
            verdict = "Đúng" if is_true else "Sai"
            answers.append(
                {
                    "statement_id": statement.get("id"),
                    "is_true": is_true,
                    "explanation": (
                        f"{verdict}. Bản ghi cũ chưa lưu giải thích khoa học cụ thể cho phát biểu "
                        f"“{_clean(statement.get('content'))}”; cần tạo lại trước khi sử dụng."
                    ),
                }
            )
        return {**base, "answers": answers}

    if question_type == "short_answer":
        correct = _clean(question.get("correct_answer") or topic or scope)
        return {
            **base,
            "correct_answer": correct,
            "keywords": correct.split()[:5] if correct else [],
            "accept_variations": True,
            "explanation": (
                f"Đáp án dự kiến là “{correct}”. Bản ghi cũ chưa lưu phép suy luận khoa học "
                "hoặc phép tính chứng minh; cần tạo lại lời giải trước khi sử dụng."
            ),
        }

    return {
        **base,
        "model_answer": (
            "Bản ghi cũ chưa có đáp án mẫu khoa học đủ chi tiết. Giáo viên cần tạo lại đáp án "
            "để nhận các ý kiến thức, lập luận và kết luận cụ thể trước khi chấm."
        ),
        "key_points": [
            "Cần tạo lại ý kiến thức khoa học thứ nhất",
            "Cần tạo lại ý kiến thức khoa học thứ hai",
        ],
    }


def normalize_answer(answer: dict | None, question: dict, spec: dict) -> dict:
    """Return a complete answer and replace all citation data with trusted data."""
    normalized = deepcopy(answer) if isinstance(answer, dict) else {}
    # Older records store truth only in answer_key. Supplement missing duplicate
    # fields for fallback prose without changing canonical truth or input JSON.
    fallback_question = deepcopy(question)
    if not _clean(question.get("correct_answer")):
        stored_correct = _clean(normalized.get("correct_answer")).upper()
        if stored_correct in (question.get("options") or {}):
            fallback_question["correct_answer"] = stored_correct
    stored_statements = {
        item.get("statement_id"): item.get("is_true")
        for item in (normalized.get("answers") or [])
        if isinstance(item, dict) and isinstance(item.get("is_true"), bool)
    }
    for statement in fallback_question.get("statements") or []:
        if not isinstance(statement.get("is_true"), bool) and statement.get("id") in stored_statements:
            statement["is_true"] = stored_statements[statement["id"]]
    fallback = _fallback_answer(fallback_question, spec)
    normalized.update({key: fallback[key] for key in ("question_id", "question_number", "type")})
    question_type = fallback["type"]

    if question_type == "multiple_choice":
        normalized["correct_answer"] = fallback["correct_answer"]
        explanation = _clean(normalized.get("explanation"))
        normalized["explanation"] = (
            explanation or fallback["explanation"]
        )
        option_explanations = normalized.get("option_explanations")
        option_labels = set((question.get("options") or {}).keys())
        if not isinstance(option_explanations, dict) or set(option_explanations) != option_labels:
            normalized["option_explanations"] = fallback["option_explanations"]
    elif question_type == "true_false":
        supplied = {
            item.get("statement_id"): item
            for item in (normalized.get("answers") or [])
            if isinstance(item, dict)
        }
        complete = []
        for fallback_item in fallback["answers"]:
            item = deepcopy(supplied.get(fallback_item["statement_id"]) or {})
            item["statement_id"] = fallback_item["statement_id"]
            item["is_true"] = fallback_item["is_true"]
            explanation = _clean(item.get("explanation"))
            item["explanation"] = (
                explanation or fallback_item["explanation"]
            )
            item.pop("citations", None)
            complete.append(item)
        normalized["answers"] = complete
    elif question_type == "short_answer":
        for key in ("correct_answer", "keywords"):
            if not normalized.get(key):
                normalized[key] = fallback[key]
        if "accept_variations" not in normalized:
            normalized["accept_variations"] = fallback["accept_variations"]
        explanation = _clean(normalized.get("explanation"))
        normalized["explanation"] = (
            explanation or fallback["explanation"]
        )
    else:
        model_answer = _clean(normalized.get("model_answer"))
        normalized["model_answer"] = model_answer or fallback["model_answer"]
        if not normalized.get("key_points"):
            normalized["key_points"] = fallback["key_points"]

    # Provider-authored citations are deliberately discarded.
    citation = _source_citation(question, spec)
    normalized["citations"] = [citation] if citation else []
    return normalized
