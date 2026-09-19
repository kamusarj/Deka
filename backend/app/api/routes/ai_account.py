"""Read only projections of the authenticated user's own AI account."""
from typing import Literal
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from app.models.user import User
from app.models.ai_account import AIUsage, CreditTransaction
from app.services.auth_service import get_current_user
from app.services.ai.credits import CreditService

router = APIRouter(prefix='/me', tags=['ai-account'])

from app.services.ai.projections import fields, LEDGER_FIELDS, usage_projection

@router.get('/subscription')
def subscription(user: User = Depends(get_current_user)):
    return CreditService().read_account(user.id)

@router.get('/credits')
def credits(user: User = Depends(get_current_user), limit: int = Query(20, ge=1, le=100),
            offset: int = Query(0, ge=0)):
    service = CreditService()
    account = service.read_account(user.id)
    with service.sessions() as db:
        rows = db.scalars(select(CreditTransaction).where(CreditTransaction.user_id == user.id)
                          .order_by(CreditTransaction.id.desc()).offset(offset).limit(limit)).all()
        return {'balance': account['credit_balance'] if account else 0, 'transactions': [fields(row, LEDGER_FIELDS) for row in rows]}

@router.get('/usage')
def usage(user: User = Depends(get_current_user), limit: int = Query(20, ge=1, le=100),
          offset: int = Query(0, ge=0), kind: Literal['request', 'provider'] = 'request',
          request_id: str | None = Query(None, max_length=36)):
    if kind == 'provider' and user.role != 'super_admin':
        raise HTTPException(403, 'Không có quyền xem metadata AI')
    service = CreditService()
    with service.sessions() as db:
        query = select(AIUsage).where(AIUsage.user_id == user.id, AIUsage.record_kind == kind)
        if request_id:
            query = query.where(AIUsage.request_id == request_id)
        rows = db.scalars(query.order_by(AIUsage.created_at.desc(), AIUsage.id.desc())
                         .offset(offset).limit(limit)).all()
        return {'items': [usage_projection(row, user) for row in rows], 'limit': limit, 'offset': offset}


@router.get('/requests/{request_id}')
def request_status(request_id: str, user: User = Depends(get_current_user)):
    service = CreditService()
    with service.sessions() as db:
        row = db.scalar(select(AIUsage).where(AIUsage.id == request_id,
            AIUsage.user_id == user.id, AIUsage.record_kind == 'request'))
        if row is None:
            raise HTTPException(404, 'Không tìm thấy yêu cầu')
        result = usage_projection(row, user)
        result['result_exam_id'] = row.result_exam_id
        return result
