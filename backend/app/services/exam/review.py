"""Teacher-review bookkeeping and small content transforms."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from app.schemas.exam import CurriculumItem


def reset_review_status(questions) -> dict:
    """Fresh review state — used when an exam is duplicated."""
    return {
        question["id"]: {"status": "pending", "regenerated": False, "reason": ""}
        for question in (questions or [])
    }


def apply_review_ids(
    review_status: dict,
    question_ids: list[str],
    valid_question_ids: set[str],
    *,
    status: str,
) -> None:
    """Stamp `status` onto each listed question, rejecting unknown ids."""
    for question_id in question_ids:
        if question_id not in valid_question_ids:
            raise HTTPException(status_code=400, detail=f"Không tìm thấy câu hỏi {question_id}")
        review_status[question_id] = {
            **review_status.get(question_id, {}),
            "status": status,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": review_status.get(question_id, {}).get("reviewed_by", "teacher"),
        }


def replace_by_id(current: list[dict], replacements: list[dict], key: str) -> list[dict]:
    """Swap matching items in place and append any replacement that is new."""
    replacement_map = {item[key]: item for item in replacements}
    replaced = [replacement_map.get(item[key], item) for item in current]
    existing_keys = {item[key] for item in replaced}
    replaced.extend(item for item in replacements if item[key] not in existing_keys)
    return replaced


def curriculum_from_text(text: str) -> list[CurriculumItem]:
    """Parse pasted syllabus lines like `Chủ đề 1: Hệ tuần hoàn (6 tiết)`."""
    curriculum = []
    for line in text.splitlines():
        cleaned = line.strip(" -\t")
        if not cleaned:
            continue
        periods = 1
        if "(" in cleaned and "tiết" in cleaned:
            before, _, after = cleaned.partition("(")
            cleaned = before.strip()
            digits = "".join(char for char in after if char.isdigit())
            periods = int(digits) if digits else 1
        curriculum.append(
            CurriculumItem(
                topic=cleaned,
                periods=periods,
                achievements=[f"Nêu và vận dụng được kiến thức trọng tâm của {cleaned}"],
            )
        )
    return curriculum
