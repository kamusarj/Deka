"""Exam ORM model -> API response mapping."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.exam import ExamResponse, FullExamResponse
from app.services.exam import variants
from app.services.exam.answer_content import normalize_answer


def normalized_answer_key(
    questions, answer_key, specification, *, default_source_name: str | None = None
) -> list[dict]:
    """Upgrade legacy answer JSON at the read boundary without rewriting it."""
    answer_by_id = {
        item.get("question_id"): item
        for item in (answer_key or [])
        if isinstance(item, dict)
    }
    spec_by_id = {
        item.get("question_id"): item
        for item in (specification or [])
        if isinstance(item, dict)
    }
    normalized = []
    for question in questions or []:
        source = question.get("source") or {}
        if default_source_name and source.get("source_name") in {
            "Local curriculum seed data",
            "Bộ dữ liệu MVP",
        }:
            question = {
                **question,
                "source": {**source, "source_name": default_source_name},
            }
        original_id = question.get("original_id") or question.get("id")
        spec = spec_by_id.get(original_id) or {
            **(question.get("metadata") or {}),
            "question_id": question.get("id"),
            "question_number": question.get("number"),
            "question_type": question.get("type"),
            "source": question.get("source"),
        }
        answer = answer_by_id.get(question.get("id")) or answer_by_id.get(original_id)
        normalized.append(normalize_answer(answer, question, spec))
    return normalized


def exam_info(exam) -> dict:
    return {
        "school": exam.school,
        "grade": exam.grade,
        "subject": exam.subject,
        "exam_type": exam.exam_type,
        "duration_minutes": exam.duration_minutes,
        "school_year": exam.school_year,
        "total_score": exam.total_score,
        "variant_count": variants.variant_count(exam),
    }


def to_response(exam) -> ExamResponse:
    source_name = ((exam.resource_package or {}).get("raw_data") or {}).get("curriculum_file")
    return ExamResponse(
        id=exam.id,
        exam_number=getattr(exam, "exam_number", None),
        owner_user_id=exam.owner_user_id,
        school_id=exam.school_id,
        publication_status=exam.publication_status or "verified",
        school=exam.school,
        grade=exam.grade,
        subject=exam.subject,
        exam_type=exam.exam_type,
        duration_minutes=exam.duration_minutes,
        school_year=exam.school_year,
        total_score=exam.total_score,
        matrix=exam.matrix,
        summary=exam.summary,
        specification=exam.specification,
        questions=exam.questions,
        answer_key=normalized_answer_key(
            exam.questions,
            exam.answer_key,
            exam.specification,
            default_source_name=source_name,
        ),
        rubric=exam.rubric,
        validation=exam.validation,
        resource_package=exam.resource_package,
        review_status=exam.review_status or {},
        created_at=exam.created_at or datetime.now(timezone.utc),
    )


def to_full_response(exam) -> FullExamResponse:
    source_name = ((exam.resource_package or {}).get("raw_data") or {}).get("curriculum_file")
    answer_key = normalized_answer_key(
        exam.questions,
        exam.answer_key,
        exam.specification,
        default_source_name=source_name,
    )
    publication_status = exam.publication_status or "verified"
    built_variants = variants.build_variants(exam) if publication_status == "verified" else []
    for variant in built_variants:
        variant["answer_key"] = normalized_answer_key(
            variant.get("questions"),
            variant.get("answer_key"),
            exam.specification,
            default_source_name=source_name,
        )
    return FullExamResponse(
        version_id=int(getattr(exam, "version_id", 1) or 1),
        id=exam.id,
        exam_number=getattr(exam, "exam_number", None),
        owner_user_id=exam.owner_user_id,
        school_id=exam.school_id,
        publication_status=publication_status,
        exam_info=exam_info(exam),
        matrix=exam.matrix,
        summary=exam.summary,
        specification=exam.specification,
        questions=exam.questions,
        answer_key=answer_key,
        rubric=exam.rubric,
        validation=exam.validation,
        resource_package=exam.resource_package,
        review_status=exam.review_status or {},
        variants=built_variants,
        created_at=exam.created_at or datetime.now(timezone.utc),
    )


def to_export_dict(exam) -> dict:
    """Flat dict consumed by the DOCX and PDF exporters."""
    return to_full_response(exam).model_dump()
