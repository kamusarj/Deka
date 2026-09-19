from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.services.question_duplicates import DuplicateDetector, compare_questions, exam_duplicate_report
from app.schemas.bank_question import BankQuestionCreate
from app.services.question_bank_service import QuestionBankService


def question(key="a", content="Bộ phận nào của cây thực hiện quang hợp chủ yếu?", **extra):
    return {"id": key, "content": content, "type": "short_answer", "difficulty": "nhan_biet", "answer": {"correct_answer": "lá"}, **extra}


def test_exact_normalizes_case_spacing_and_punctuation():
    a = question()
    b = question("b", "  BỘ PHẬN NÀO CỦA CÂY THỰC HIỆN QUANG HỢP CHỦ YẾU! ")
    result = compare_questions(a, b)
    assert result["duplicate_type"] == "exact" and result["decision"] == "reject"


def test_same_stem_conflicting_answer_warns():
    match = compare_questions(question(), question("b", answer={"correct_answer": "rễ"}))
    assert match["decision"] == "warn"


def test_fuzzy_typo_and_threshold(monkeypatch):
    a, b = question(), question("b", "Bộ phận nào của cây thực hiện quang hợp chủ yếuu?")
    assert compare_questions(a, b)["duplicate_type"] == "fuzzy"
    monkeypatch.setattr(settings, "DUPLICATE_FUZZY_THRESHOLD", 1)
    assert compare_questions(a, b) is None


@pytest.mark.parametrize("similarity,confirmed", [(0.859999, None), (0.86, False), (0.939999, False), (0.94, True), (1.0, True)])
def test_semantic_threshold_edges(similarity, confirmed):
    a, b = question(), question("b", "Cơ quan quang hợp chính ở thực vật là gì?")
    result = compare_questions(a, b, vector_score=similarity)
    assert (result is None) if confirmed is None else result["is_duplicate"] is confirmed


def test_different_numeric_data_and_reasoning_are_not_duplicates():
    a = question(content="Tính vận tốc khi s=100m, t=20s", answer={"correct_answer": "5 m/s"})
    b = question("b", "Tính vận tốc khi s=180m, t=30s", answer={"correct_answer": "6 m/s"})
    assert compare_questions(a, b, vector_score=1) is None
    assert compare_questions(question(reasoning_mode="causal"), question("b", reasoning_mode="experimental"), vector_score=1) is None


def test_shared_objective_does_not_make_duplicate():
    a = question(metadata={"knowledge_target": "quang hợp"})
    b = question("b", "Quang hợp sử dụng khí gì?", answer={"correct_answer": "carbon dioxide"}, metadata={"knowledge_target": "quang hợp"})
    assert compare_questions(a, b, vector_score=0.98) is None


def test_mcq_equivalence_uses_option_content_not_labels():
    a = question(type="multiple_choice", options={"A": "lá", "B": "rễ"}, answer={"correct_answer": "A"})
    b = question("b", type="multiple_choice", options={"B": "lá", "A": "rễ"}, answer={"correct_answer": "B"})
    assert compare_questions(a, b)["duplicate_type"] == "exact"


class SemanticEmbedder:
    name = "duplicate-unit-test"
    def embed(self, texts):
        return [[1.0, 0.0] for text in texts]
    def embed_query(self, text):
        return [1.0, 0.0]


def test_semantic_detector_and_provider_failure():
    detector = DuplicateDetector([question("b", "Cơ quan quang hợp chính ở thực vật là gì?")], embedder=SemanticEmbedder())
    assert detector.check(question())[0]["duplicate_type"] == "semantic"
    assert detector.check(question(), exclude_ids=["b"]) == []
    detector.vector.retrieve = lambda *a: (_ for _ in ()).throw(RuntimeError("offline"))
    detector.check(question())
    assert detector.semantic_available is False


def test_exam_and_bank_findings_have_distinct_scopes():
    a, b = question(), question("b")
    result = exam_duplicate_report([a, b], [], [question("42")], embedder=SemanticEmbedder())
    assert {item["scope"] for item in result["findings"]} == {"bank", "exam"}
    assert len([f for f in result["findings"] if f["scope"] == "exam"]) == 1
    assert a == question()  # no mutation of teacher/generation content


def test_bank_rejects_exact_repeat_but_other_actor_cannot_discover_it(auth_context, admin_auth_context):
    service = QuestionBankService()
    payload = BankQuestionCreate(content=f"Quang hợp {uuid4().hex}", type="short_answer", answer={"correct_answer": "lá"}, grade=8)
    teacher = auth_context["user"]
    saved = service.add_question(payload, actor=teacher)
    try:
        with pytest.raises(HTTPException) as error:
            service.add_question(payload, actor=teacher)
        assert error.value.status_code == 409
        assert service.semantic_search(payload.content, actor=admin_auth_context["user"]) == []
        hits = service.semantic_search(payload.content, actor=teacher)
        assert hits[0]["question"]["id"] == saved.id
    finally:
        service.delete_question(saved.id, actor=teacher)


def test_semantic_warning_against_persisted_bank_uses_shared_embedder(auth_context, monkeypatch):
    import app.services.question_duplicates as duplicates
    monkeypatch.setattr(duplicates, 'resolve_embedder', lambda: SemanticEmbedder())
    service = QuestionBankService()
    actor = auth_context['user']
    saved = []
    try:
        first = service.add_question(BankQuestionCreate(content='Bộ phận nào của cây thực hiện quang hợp chủ yếu?', type='short_answer', difficulty='nhan_biet', grade=7, answer={'correct_answer': 'lá'}), actor=actor)
        saved.append(first.id)
        second = service.add_question(BankQuestionCreate(content='Cơ quan quang hợp chính ở thực vật là gì?', type='short_answer', difficulty='nhan_biet', grade=8, answer={'correct_answer': 'lá'}), actor=actor)
        saved.append(second.id)
        finding = next(f for f in second.duplicate_findings if f['duplicate_type'] == 'semantic')
        assert finding['matched_question_id'] == str(first.id)
        assert finding['severity'] == 'WARNING' and finding['is_duplicate']
    finally:
        for key in saved:
            service.delete_question(key, actor=actor)


def test_legacy_nullable_tf_answers_do_not_break_duplicate_pipeline():
    a = question(type='true_false', statements=[{'id': 's1', 'content': 'Lá quang hợp.', 'is_true': True}], answer={'answers': None})
    b = {**deepcopy(a), 'id': 'legacy'}
    assert compare_questions(a, b)['duplicate_type'] == 'exact'


def test_legacy_non_scalar_mcq_answer_does_not_crash_candidate_comparison():
    a = question(type='multiple_choice', options={'A': 'lá', 'B': 'rễ'}, answer={'correct_answer': ['A']})
    assert compare_questions(a, {**deepcopy(a), 'id': 'legacy'}) is not None
