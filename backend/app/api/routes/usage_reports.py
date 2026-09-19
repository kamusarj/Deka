"""Public plan catalog, scoped reports, and audited Super Admin account settings."""
from datetime import date
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_db
from app.models.ai_account import AIUsage, CreditTransaction, UserSubscription
from app.models.user import User
from app.services.ai.credits import next_month, utcnow
from app.services.ai.pricing import PLAN_ALLOWANCES
from app.services.ai.reporting import metrics, projection, report, scoped_user, window
from app.services.audit_service import record_audit
from app.services.auth_service import get_current_user, require_super_admin
from app.services.ai.projections import subscription_projection, usage_projection, metrics_projection
from app.services.ai.credits import CreditService, MAX_CREDIT_BALANCE

router = APIRouter(tags=['subscription-reports'])
Role = Literal['super_admin', 'school_admin', 'teacher', 'viewer']


@router.get('/subscription-plans')
def plans():
    return {'development': True, 'plans': [{'id': key, 'monthly_credits': value} for key, value in PLAN_ALLOWANCES.items()]}


@router.get('/usage/report')
def usage_report(date_from: date | None = None, date_to: date | None = None,
                 role: Role | None = None, search: str = Query('', max_length=100),
                 user_id: int | None = Query(None, ge=1), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                 actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return report(db, actor, date_from, date_to, role, search.strip(), user_id, limit, offset)


@router.get('/usage/users/{user_id}')
def user_usage(user_id: int, date_from: date | None = None, date_to: date | None = None,
               limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
               actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = scoped_user(db, actor, user_id)
    _, _, lower, upper = window(date_from, date_to)
    query = select(AIUsage).where(AIUsage.user_id == user_id, AIUsage.record_kind == 'request',
                                  AIUsage.created_at >= lower, AIUsage.created_at < upper)
    subscription = db.scalar(select(UserSubscription).where(UserSubscription.user_id == user_id))
    summary = db.execute(select(*metrics()).where(AIUsage.user_id == user_id,
                         AIUsage.created_at >= lower, AIUsage.created_at < upper)).mappings().one()
    return {'user': {'id': target.id, 'name': target.name, 'email': target.email, 'role': target.role},
            'subscription': subscription_projection(subscription),
            'summary': metrics_projection(projection(summary), actor),
            'items': [usage_projection(row, actor) for row in db.scalars(query.order_by(AIUsage.created_at.desc(), AIUsage.id.desc()).limit(limit).offset(offset))],
            'total': db.scalar(select(func.count()).select_from(query.subquery())), 'limit': limit, 'offset': offset}


class SubscriptionUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plan: str = Field(min_length=1, max_length=40)
    status: Literal['active', 'paused']
    credit_allowance: int = Field(ge=0, le=1_000_000, strict=True)
    credit_adjustment: int = Field(default=0, ge=-1_000_000, le=1_000_000, strict=True)
    settings_version: int = Field(ge=0, strict=True)  # 0 means not enrolled yet
    reason: str = Field(min_length=1, max_length=200)


@router.patch('/admin/users/{user_id}/subscription')
def update_subscription(user_id: int, payload: SubscriptionUpdate,
                        actor: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    if payload.plan not in PLAN_ALLOWANCES or not payload.reason.strip():
        raise HTTPException(422, 'Gói hoặc lý do không hợp lệ')
    target = scoped_user(db, actor, user_id)
    # A separate short transaction avoids holding the request/auth read transaction
    # through writes. Audit, balance and ledger still commit together.
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    with factory.begin() as tx:
        if payload.settings_version == 0:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            insert = sqlite_insert if tx.bind.dialect.name == 'sqlite' else pg_insert
            now = utcnow()
            inserted = tx.execute(insert(UserSubscription).values(user_id=user_id, plan='FREE', status='active',
                credit_allowance=PLAN_ALLOWANCES['FREE'], credit_balance=PLAN_ALLOWANCES['FREE'],
                current_period_start=now, current_period_end=next_month(now), settings_version=1)
                .on_conflict_do_nothing(index_elements=['user_id']))
            if not inserted.rowcount:
                raise HTTPException(409, 'Gói đã thay đổi. Hãy tải lại tài khoản trước khi lưu.')
            tx.add(CreditTransaction(user_id=user_id, amount=PLAN_ALLOWANCES['FREE'], type='subscription',
                                    reference_id='initial', description='Development FREE allowance'))
        expected = payload.settings_version or 1
        claimed = tx.execute(update(UserSubscription).where(UserSubscription.user_id == user_id,
                UserSubscription.settings_version == expected).values(settings_version=UserSubscription.settings_version + 1))
        if not claimed.rowcount:
            raise HTTPException(409, 'Gói đã thay đổi. Hãy tải lại tài khoản trước khi lưu.')
        account = tx.scalar(select(UserSubscription).where(UserSubscription.user_id == user_id))
        before = {name: getattr(account, name) for name in ['plan', 'status', 'credit_allowance', 'credit_balance']}
        if account.credit_balance + payload.credit_adjustment < 0:
            raise HTTPException(409, 'Số dư không đủ để trừ credit. Hãy tải lại tài khoản.')
        if account.credit_balance + payload.credit_adjustment + CreditService.held(tx, user_id) > MAX_CREDIT_BALANCE:
            raise HTTPException(422, 'Số dư vượt giới hạn cho phép')
        account.plan, account.status = payload.plan, payload.status
        account.credit_allowance = payload.credit_allowance
        account.credit_balance += payload.credit_adjustment
        if payload.credit_adjustment:
            tx.add(CreditTransaction(user_id=user_id, amount=payload.credit_adjustment, type='adjustment',
                                    reference_id=str(uuid4()), description=payload.reason.strip()))
        after = {name: getattr(account, name) for name in before}
        record_audit(tx, actor=actor, action='subscription.updated', target_type='user_subscription',
                     target_id=user_id, school_id=target.school_id,
                     details={'before': before, 'after': after, 'reason': payload.reason.strip(), 'settings_version': account.settings_version})
        tx.flush()
        result = subscription_projection(account)
    return result
