from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.question_edit import QuestionEditRequest
from app.services.exam.editing import merge_edit
from app.services.exam_service import ExamService
from app.schemas.exam import FullExamRequest, RegenerateQuestionsRequest
from tests.test_question_bank import exam_payload, make_exam_service


def mcq():
    return {"id": "q_1", "number": 1, "content": "Lá cây có vai trò nào?", "type": "multiple_choice", "difficulty": "nhan_biet", "score": 1,
            "options": {"A": "Quang hợp", "B": "Hút nước", "C": "Vận chuyển", "D": "Sinh sản"}, "correct_answer": "A",
            "metadata": {"knowledge_target": "lá", "reasoning_mode": "conceptual", "knowledge_intent": "function"}, "source": {"source_name": "SGK"}}


def mcq_edit(**overrides):
    data = {"version_id": 1, "content": "Lá cây thực hiện chức năng nào?", "options": mcq()["options"], "correct_answer": "A", "explanation": "Lá có lục lạp chứa diệp lục để hấp thụ ánh sáng và thực hiện quang hợp.",
            "option_explanations": {key: "Phương án được đối chiếu theo chức năng của từng cơ quan trong cây." for key in "ABCD"}}
    data.update(overrides)
    return QuestionEditRequest(**data)


def test_teacher_edit_preserves_domain_and_source_without_mutating_original():
    original = mcq()
    edited, answer, _ = merge_edit(original, {"correct_answer": "A", "citations": [{"excerpt": "source"}]}, None, mcq_edit())
    assert original == mcq()
    assert edited["source"] == original["source"]
    assert all(edited["metadata"][key] == value for key, value in original["metadata"].items())
    assert edited["metadata"]["revision"] == 1 and edited["metadata"]["teacher_edited"]
    assert answer["citations"] == [{"excerpt": "source"}]


@pytest.mark.parametrize("field,value", [("type", "essay"), ("score", 99), ("metadata", {}), ("source", {})])
def test_edit_schema_rejects_domain_and_provenance_overrides(field, value):
    with pytest.raises(ValidationError):
        QuestionEditRequest(**{**mcq_edit().model_dump(), field: value})


def test_invalid_mcq_answer_or_duplicate_options_rejected():
    with pytest.raises(HTTPException):
        merge_edit(mcq(), {}, None, mcq_edit(correct_answer="Z"))
    with pytest.raises(HTTPException):
        merge_edit(mcq(), {}, None, mcq_edit(options={key: "lá" for key in "ABCD"}))


def test_true_false_edits_keep_truth_and_explanation_with_statement():
    original = {**mcq(), "type": "true_false", "options": None, "statements": [{"id": f"s{i}", "content": "Lá chứa diệp lục để hấp thụ ánh sáng.", "is_true": True} for i in range(4)]}
    statements = [{**item, "explanation": "Lá có các tế bào chứa lục lạp thực hiện quang hợp."} for item in original["statements"]]
    statements[0].update(is_true=False, explanation="Phát biểu sai vì thực tế rễ hấp thụ nước, lá thực hiện quang hợp.")
    edited, answer, _ = merge_edit(original, {}, None, QuestionEditRequest(version_id=1, content=original["content"], statements=statements))
    assert edited["statements"][0]["is_true"] is False
    assert answer["answers"][0]["statement_id"] == "s0" and answer["answers"][0]["is_true"] is False
    statements[0]["id"] = "unknown"
    with pytest.raises(HTTPException):
        merge_edit(original, {}, None, QuestionEditRequest(version_id=1, content=original["content"], statements=statements))


def test_essay_edit_validates_rubric_score_and_preserves_subquestion_ids():
    q = {**mcq(), "type": "essay", "options": None, "sub_questions": [{"id": "s1", "content": "Nêu vai trò của lá.", "score": 0.5}, {"id": "s2", "content": "Giải thích vai trò của rễ.", "score": 0.5}]}
    criteria = [{"id": f"c{i}", "name": name, "max_score": 0.5, "levels": [{"score": 0.5, "description": name}]} for i, name in enumerate(["Lá cây thực hiện quang hợp", "Rễ cây hấp thụ nước"])]
    request = QuestionEditRequest(version_id=1, content=q["content"], explanation="Mỗi cơ quan thực hiện một chức năng.", model_answer="Lá chứa diệp lục để thực hiện quang hợp, còn rễ hấp thụ nước và muối khoáng từ đất.", sub_questions=q["sub_questions"], rubric_criteria=criteria)
    edited, answer, rubric = merge_edit(q, {}, None, request)
    assert rubric["total_score"] == 1 and len(answer["key_points"]) == 2
    assert edited["sub_questions"][0]["id"] == "s1"
    request.rubric_criteria[0].max_score = 1
    with pytest.raises(HTTPException):
        merge_edit(q, {}, None, request)


@pytest.mark.asyncio
async def test_service_edit_persists_draft_when_review_unavailable_and_rejects_stale_version(auth_context):
    service = make_exam_service()
    exam = await service.generate_full_exam(FullExamRequest(**exam_payload()), actor=auth_context["user"])
    q = exam.questions[0]
    answer = next(a for a in exam.answer_key if a["question_id"] == q["id"])
    payload = mcq_edit(version_id=exam.version_id, content=q["content"], options=q["options"], correct_answer=answer["correct_answer"])
    saved = await service.edit_question(exam.id, q["id"], payload, actor=auth_context["user"])
    assert saved.version_id > exam.version_id
    assert saved.questions[0]["metadata"]["teacher_edited"] is True
    assert saved.publication_status == "draft"
    with pytest.raises(HTTPException) as error:
        await service.edit_question(exam.id, q["id"], payload, actor=auth_context["user"])
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        await service.export_docx(exam.id, actor=auth_context["user"])
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_edit_cannot_mutate_another_teachers_exam(auth_context, admin_auth_context):
    service = make_exam_service()
    exam = await service.generate_full_exam(FullExamRequest(**exam_payload()), actor=auth_context["user"])
    with pytest.raises(HTTPException) as error:
        await service.edit_question(exam.id, exam.questions[0]["id"], mcq_edit(), actor=admin_auth_context["user"])
    assert error.value.status_code == 404
