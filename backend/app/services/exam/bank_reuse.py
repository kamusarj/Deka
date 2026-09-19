"""Adapt an authorized bank item into the existing teacher edit contract."""
from copy import deepcopy
from fastapi import HTTPException
from pydantic import ValidationError
from app.schemas.question_edit import QuestionEditRequest


def bank_edit_template(bank, question, version):
    answer = bank.answer or {}
    rubric = answer.get('rubric') or {}
    answer = answer.get('answer', answer)
    if bank.type != question['type'] or bank.difficulty != question['difficulty']:
        raise HTTPException(422, 'Câu ngân hàng phải cùng dạng và mức độ với ô đặc tả.')
    payload = {'bank_question_id': bank.id, 'version_id': version, 'content': bank.content,
               'rich_content': bank.rich_content or [], 'explanation': answer.get('explanation', '')}
    if bank.type == 'multiple_choice':
        payload.update(options=bank.options, correct_answer=answer.get('correct_answer'), option_explanations=answer.get('option_explanations'))
    elif bank.type == 'short_answer':
        payload['correct_answer'] = answer.get('correct_answer')
    elif bank.type == 'true_false':
        statements = bank.statements or []
        originals = question.get('statements') or []
        if len(statements) != 4 or len(originals) != 4:
            raise HTTPException(422, 'Câu đúng/sai cần đủ bốn phát biểu.')
        answers = {a['statement_id']: a for a in answer.get('answers', [])}
        payload['statements'] = [{'id': old['id'], 'content': item['content'], 'is_true': answers.get(item['id'], {}).get('is_true', item.get('is_true')), 'explanation': answers.get(item['id'], {}).get('explanation', '')} for old, item in zip(originals, statements)]
    else:
        rubric = answer.get('rubric') or rubric
        parts, originals = bank.sub_questions or [], question.get('sub_questions') or []
        if len(parts) != len(originals) or abs(float(rubric.get('total_score', -1)) - question['score']) > 1e-6:
            raise HTTPException(422, 'Câu tự luận cần cùng số ý và tổng điểm để giữ ma trận.')
        payload.update(model_answer=answer.get('model_answer'), rubric_criteria=rubric.get('criteria'),
                       sub_questions=[{**deepcopy(item), 'id': old['id']} for old, item in zip(originals, parts)])
    try:
        return QuestionEditRequest.model_validate(payload)
    except (ValidationError, TypeError) as error:
        raise HTTPException(422, 'Câu ngân hàng cũ thiếu dữ liệu cần thiết để chỉnh sửa. Hãy bổ sung đáp án/lời giải trước.') from error
