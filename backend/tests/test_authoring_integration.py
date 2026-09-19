from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text

from app.core.database import _migrate_compatibility_columns
from app.schemas.exam import FullExamRequest
from app.schemas.bank_question import SaveFromExamRequest
from app.services.exam.editing import validate_revision
from app.services.exam_service import ExamService
from app.services.question_bank_service import QuestionBankService
from tests.test_question_bank import make_exam_service, exam_payload
from tests.test_khtn_generation_quality import spec, speed_calculation, speed_question, valid_function_mc


def test_additive_rich_columns_preserve_legacy_data(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path}/legacy.db')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE bank_questions (id INTEGER PRIMARY KEY, content TEXT)'))
        connection.execute(text("INSERT INTO bank_questions (id,content) VALUES (1,'Legacy text')"))
    _migrate_compatibility_columns(engine)
    _migrate_compatibility_columns(engine)
    assert {'rich_content', 'content_metadata'} <= {c['name'] for c in inspect(engine).get_columns('bank_questions')}
    with engine.connect() as connection:
        assert connection.execute(text('SELECT content,rich_content FROM bank_questions')).one() == ('Legacy text', None)


@pytest.mark.asyncio
async def test_editor_revalidates_numeric_proof_with_existing_formula_gate():
    item = spec('Tính được tốc độ từ quãng đường và thời gian.', topic='Tốc độ', difficulty='van_dung', source_context='Tốc độ bằng quãng đường chia thời gian: v = s / t.')
    item['requires_calculation'] = True
    question = {**speed_question(), 'difficulty': 'van_dung', 'score': 1, 'metadata': {'is_calculation': True, 'calculation_verified': True}}
    answer = {'correct_answer': 'A', 'explanation': 'Đổi 1,5 km thành 1500 m, 5 phút thành 300 s rồi chia quãng đường cho thời gian được 5 m/s.', 'option_explanations': {key: 'Đối chiếu kết quả tính tốc độ sau khi chuyển đổi đơn vị.' for key in 'ABCD'}}
    llm = SimpleNamespace(generate_json=Mock(return_value=speed_calculation()))
    await validate_revision(question, answer, None, item, grade=7, llm=llm)
    assert question['metadata']['calculation_verified']
    question['options']['A'] = '7 m/s'
    issues = await validate_revision(question, answer, None, item, grade=7, llm=llm)
    assert not question['metadata']['calculation_verified']
    assert 'correct_option_numeric_mismatch' in {issue.code for issue in issues}


@pytest.mark.asyncio
async def test_editor_runs_domain_gate_for_non_numeric_edits():
    question, answer = valid_function_mc()
    question['content'] = 'Theo yêu cầu cần đạt, có thể bỏ qua kiến thức này.'
    llm = SimpleNamespace(generate_json=Mock())
    issues = await validate_revision(question, answer, None, spec('Nêu được chức năng của tim.'), grade=8, llm=llm)
    assert 'meta_learning_language' in {issue.code for issue in issues}
    llm.generate_json.assert_not_called()


@pytest.mark.asyncio
async def test_bank_reuse_template_preserves_matrix_and_enforces_ownership(auth_context, admin_auth_context):
    service = make_exam_service()
    actor = auth_context['user']
    exam = await service.generate_full_exam(FullExamRequest(**exam_payload()), actor=actor)
    bank = QuestionBankService()
    saved = bank.save_from_exam(SaveFromExamRequest(exam_id=exam.id, question_ids=[exam.questions[0]['id']]), actor=actor).saved[0]
    try:
        q = exam.questions[0]
        template = service.bank_edit_template(exam.id, q['id'], saved.id, version_id=exam.version_id, actor=actor)
        assert template.content == q['content'] and template.bank_question_id == saved.id
        assert template.version_id == exam.version_id
        with pytest.raises(HTTPException) as error:
            service.bank_edit_template(exam.id, q['id'], saved.id, version_id=exam.version_id, actor=admin_auth_context['user'])
        assert error.value.status_code == 404
        with pytest.raises(HTTPException) as error:
            service.bank_edit_template(exam.id, q['id'], saved.id, version_id=exam.version_id+1, actor=actor)
        assert error.value.status_code == 409
        assert (await service.get_exam(exam.id, actor=actor)).questions == exam.questions
    finally:
        bank.delete_question(saved.id, actor=actor)
