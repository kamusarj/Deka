"""SQL-only scoped accounting projections. Request summaries never duplicate cost."""
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select

from app.models.ai_account import AIUsage as U, UserSubscription
from app.models.user import User
from app.services.role_policy import KNOWN_ROLES


def scope(actor, *, history=False):
    if actor.role not in KNOWN_ROLES:
        raise HTTPException(403, 'Không có quyền xem báo cáo')
    active = User.deleted_at.is_(None)
    if actor.role == 'super_admin':
        return User.id.is_not(None) if history else active
    if actor.role == 'school_admin' and actor.school_id is not None:
        return and_(active, or_(User.id == actor.id, and_(User.school_id == actor.school_id, User.role == 'teacher')))
    return and_(active, User.id == actor.id)


def scoped_user(db, actor, user_id):
    target = db.scalar(select(User).where(scope(actor), User.id == user_id))
    if target is None:
        raise HTTPException(404, 'Không tìm thấy tài khoản trong phạm vi quản lý')
    return target


def window(date_from, date_to):
    today = datetime.now(timezone.utc).date()
    end = date_to or today
    start = date_from or end - timedelta(days=29)
    if start > end or (end - start).days >= 366:
        raise HTTPException(422, 'Khoảng thời gian phải từ 1 đến 366 ngày')
    return start, end, datetime.combine(start, time.min, timezone.utc), datetime.combine(end + timedelta(days=1), time.min, timezone.utc)


def metrics():
    request = U.record_kind == 'request'
    provider = U.record_kind == 'provider'
    def total(condition, value=1):
        return func.coalesce(func.sum(case((condition, value), else_=0)), 0)
    return [
        total(request).label('requests'),
        total(and_(request, U.status == 'success')).label('success'),
        total(and_(request, U.status == 'failed')).label('failed'),
        total(and_(request, U.status == 'reserved')).label('pending'),
        total(request, U.credits_charged).label('credits_charged'),
        total(request, U.reserved_credits).label('reserved_credits'),
        total(provider).label('provider_calls'),
        total(provider, U.input_tokens).label('input_tokens'),
        total(provider, U.output_tokens).label('output_tokens'),
        total(and_(provider, or_(U.input_tokens.is_(None), U.output_tokens.is_(None)))).label('unknown_token_calls'),
        total(provider, U.estimated_cost_usd).label('known_cost_usd'),
        total(and_(provider, U.estimated_cost_usd.is_(None))).label('unpriced_calls'),
    ]


def projection(row):
    data = dict(row)
    known = Decimal(data['known_cost_usd'] or 0)
    data['known_cost_usd'] = str(known)
    data['estimated_cost_usd'] = None if data['unpriced_calls'] else str(known)
    return data


def report(db, actor, date_from=None, date_to=None, role=None, search='', user_id=None, limit=20, offset=0):
    start, end, lower, upper = window(date_from, date_to)
    conditions = [scope(actor)]
    if user_id is not None:
        scoped_user(db, actor, user_id)
        conditions.append(User.id == user_id)
    if role:
        conditions.append(User.role == role)
    if search:
        conditions.append(or_(User.name.icontains(search, autoescape=True), User.email.icontains(search, autoescape=True)))
    history_conditions = [scope(actor, history=True), *conditions[1:]]
    usage_scope = [*history_conditions, U.created_at >= lower, U.created_at < upper]
    aggregate = select(*metrics()).select_from(U).join(User, User.id == U.user_id).where(*usage_scope)
    summary = projection(db.execute(aggregate).mappings().one())
    summary['active_users'] = db.scalar(select(func.count(func.distinct(U.user_id))).join(User, User.id == U.user_id)
                                       .where(*usage_scope, U.record_kind == 'request'))
    utc_day = func.date(func.timezone('UTC', U.created_at)) if db.get_bind().dialect.name == 'postgresql' else func.date(U.created_at)
    daily = db.execute(aggregate.add_columns(utc_day.label('day'))
                       .group_by(utc_day).order_by(utc_day)).mappings().all()
    roles = db.execute(aggregate.add_columns(User.role.label('role')).group_by(User.role).order_by(User.role)).mappings().all()
    counts = select(U.user_id.label('owner'), *metrics()).where(U.created_at >= lower, U.created_at < upper).group_by(U.user_id).subquery()
    query = select(User.id, User.name, User.email, User.role, User.is_active,
                   UserSubscription.plan, UserSubscription.credit_balance, *[counts.c[c] for c in counts.c.keys() if c != 'owner'])\
        .outerjoin(UserSubscription, UserSubscription.user_id == User.id).outerjoin(counts, counts.c.owner == User.id).where(*conditions)
    rows = db.execute(query.order_by(func.coalesce(counts.c.requests, 0).desc(), User.id).limit(limit).offset(offset)).mappings().all()
    items = []
    metric_names = [column.name for column in metrics()]
    for row in rows:
        data = dict(row)
        for name in metric_names:
            data[name] = data[name] or 0
        items.append(projection(data))
    from app.services.ai.projections import metrics_projection
    safe = lambda value: metrics_projection(value, actor)
    return {'role_semantics': 'current', 'request_time': 'request_started_at', 'cost_time': 'attempt_recorded_at', 'includes_deleted_history': actor.role == 'super_admin', 'scope': 'platform' if actor.role == 'super_admin' else 'school' if actor.role == 'school_admin' and actor.school_id else 'self',
            'date_from': start, 'date_to': end, 'timezone': 'UTC', 'summary': safe(summary),
            'daily': [safe(projection(row)) for row in daily], 'roles': [safe(projection(row)) for row in roles],
            'users': [safe(item) for item in items], 'total_users': db.scalar(select(func.count(User.id)).where(*conditions)), 'limit': limit, 'offset': offset}
