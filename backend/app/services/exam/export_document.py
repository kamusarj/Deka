"""Select one document and one paper without modifying stored exam data."""

from copy import deepcopy
from typing import Literal

from fastapi import HTTPException

ExportDocument = Literal["exam", "answers", "matrix", "specification"]

DOCUMENT_TITLES = {
    "exam": "Đề kiểm tra",
    "answers": "Đáp án và hướng dẫn chấm",
    "matrix": "Ma trận đề kiểm tra",
    "specification": "Bản đặc tả đề kiểm tra",
}


def select_export_data(exam_data: dict, variant_code: str | None = None) -> dict:
    data = deepcopy(exam_data)
    data["variant_code"] = variant_code
    if not variant_code:
        return data
    selected = next(
        (item for item in data.get("variants", []) if item["code"] == variant_code),
        None,
    )
    if selected is None:
        raise HTTPException(status_code=404, detail="Mã đề không tồn tại trong đề kiểm tra này")
    data["questions"] = selected["questions"]
    data["answer_key"] = selected["answer_key"]
    by_id = {q.get("original_id"): q for q in selected["questions"] if q.get("original_id")}
    by_number = {q.get("original_number"): q for q in selected["questions"] if q.get("original_number")}
    for section in ("rubric", "specification"):
        for item in data.get(section, []):
            question = by_id.get(item.get("question_id")) or by_number.get(item.get("question_number"))
            if question:
                item["question_id"] = question["id"]
                item["question_number"] = question["number"]
        data[section] = sorted(data.get(section, []), key=lambda item: item.get("question_number", 0))
    return data


def require_export_document(document: str, include_answers: bool) -> None:
    if document not in DOCUMENT_TITLES:
        raise HTTPException(status_code=422, detail="Loại tài liệu xuất không hợp lệ")
    if not include_answers and document != "exam":
        raise HTTPException(status_code=422, detail="Bản học sinh chỉ xuất đề kiểm tra")
