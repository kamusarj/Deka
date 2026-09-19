"""Short SQL transactions; never hold a database lock across provider work."""
from calendar import monthrange
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.config import settings
from app.core.database import get_session_factory
from app.models.ai_account import AIUsage, CreditTransaction, UserSubscription
from app.models.user import User
from app.services.ai.errors import AIError
from app.services.ai.pricing import PLAN_ALLOWANCES
from app.services.ai.policy import operation_policy

MAX_CREDIT_BALANCE = 2_000_000_000
from app.services.ai.usage import summarize_request


def utcnow():
    return datetime.now(timezone.utc)


def next_month(now):
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    return now.replace(year=year, month=month, day=min(now.day, monthrange(year, month)[1]))


class CreditService:
    def __init__(self, session_factory=None):
        self.sessions = session_factory or get_session_factory()

    def read_account(self, user_id):
        from app.services.ai.projections import subscription_projection
        with self.sessions() as db:
            return subscription_projection(db.scalar(select(UserSubscription).where(UserSubscription.user_id == user_id)))

    @staticmethod
    def held(db, user_id):
        return db.scalar(select(func.coalesce(func.sum(AIUsage.reserved_credits), 0)).where(
            AIUsage.user_id == user_id, AIUsage.record_kind == 'request', AIUsage.status == 'reserved'))

    def account(self, user_id):
        """Enroll once and lazily grant one current month, without missed-month backpay.

        Initial insert and each grant commit with their ledger row. UNIQUE/CAS
        protects simultaneous first visits and renewals on SQLite and Postgres.
        """
        now = utcnow()
        with self.sessions.begin() as db:
            if db.get(User, user_id) is None:
                raise HTTPException(404, 'Không tìm thấy tài khoản')
            insert = sqlite_insert if db.bind.dialect.name == 'sqlite' else pg_insert
            allowance = PLAN_ALLOWANCES['FREE']
            if type(allowance) is not int or not 0 <= allowance <= MAX_CREDIT_BALANCE:
                raise AIError('AI_CREDIT_CONFIGURATION_ERROR', 503)
            result = db.execute(insert(UserSubscription).values(
                user_id=user_id, plan='FREE', status='active', credit_allowance=allowance,
                credit_balance=allowance, current_period_start=now, current_period_end=next_month(now),
            ).on_conflict_do_nothing(index_elements=['user_id']))
            if result.rowcount:
                db.add(CreditTransaction(user_id=user_id, amount=allowance, type='subscription',
                       reference_id='initial', description='Development FREE allowance'))
            db.execute(update(UserSubscription).where(UserSubscription.user_id == user_id)
                       .values(credit_balance=UserSubscription.credit_balance))
            pending = self.held(db, user_id)
            renewed = db.execute(update(UserSubscription).where(
                UserSubscription.user_id == user_id, UserSubscription.status == 'active',
                UserSubscription.current_period_end <= now,
                UserSubscription.credit_balance + UserSubscription.credit_allowance <= MAX_CREDIT_BALANCE - pending,
            ).values(credit_balance=UserSubscription.credit_balance + UserSubscription.credit_allowance,
                     current_period_start=now, current_period_end=next_month(now)))
            account = db.scalar(select(UserSubscription).where(UserSubscription.user_id == user_id))
            if renewed.rowcount:
                db.add(CreditTransaction(user_id=user_id, amount=account.credit_allowance,
                       type='subscription', reference_id=f'period:{now.isoformat()}',
                       description='Development monthly allowance; unused credits carry over'))
            db.flush()
            return {column.name: getattr(account, column.name) for column in account.__table__.columns}

    def reserve(self, user_id, operation, *, lease_owner=None, idempotency_key=None, fingerprint=None):
        policy = operation_policy(operation)
        self.account(user_id)
        amount = policy.credits if settings.ENABLE_CREDIT_SYSTEM else 0
        request_id = str(uuid4())
        with self.sessions.begin() as db:
            # Serialize per-account admission and deduplication before debit.
            db.execute(update(UserSubscription).where(UserSubscription.user_id == user_id)
                       .values(credit_balance=UserSubscription.credit_balance))
            if idempotency_key:
                previous = db.scalar(select(AIUsage).where(AIUsage.user_id == user_id,
                    AIUsage.operation == operation, AIUsage.idempotency_key == idempotency_key))
                if previous:
                    if previous.input_fingerprint != fingerprint:
                        raise AIError('AI_IDEMPOTENCY_CONFLICT', 409)
                    raise RequestReplay(previous.id)
            # Single deployed worker plus a DB transaction lock also protects
            # admission when operators run a second process by mistake.
            if db.bind.dialect.name == 'postgresql':
                db.execute(text('SELECT pg_advisory_xact_lock(184005)'))
            day = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            requests = db.scalar(select(func.count()).select_from(AIUsage).where(
                AIUsage.record_kind == 'request', AIUsage.created_at >= day))
            cost = db.scalar(select(func.coalesce(func.sum(AIUsage.estimated_cost_usd), 0)).where(
                AIUsage.record_kind == 'provider', AIUsage.created_at >= day))
            if requests >= settings.AI_DAILY_REQUEST_LIMIT or cost >= settings.AI_DAILY_COST_LIMIT_USD:
                raise AIError('AI_BUDGET_EXCEEDED', 429)
            reserved = db.execute(update(UserSubscription).where(
                UserSubscription.user_id == user_id, UserSubscription.status == 'active',
                UserSubscription.credit_balance >= amount,
            ).values(credit_balance=UserSubscription.credit_balance - amount))
            if not reserved.rowcount:
                account = db.scalar(select(UserSubscription).where(UserSubscription.user_id == user_id))
                if account is not None and account.status != 'active':
                    raise AIError('SUBSCRIPTION_INACTIVE', 403)
                raise AIError('INSUFFICIENT_CREDITS', 402)
            db.add(AIUsage(id=request_id, request_id=request_id, user_id=user_id,
                          operation=operation, record_kind='request', status='reserved',
                          reserved_credits=amount, lease_owner=lease_owner,
                          lease_expires_at=utcnow() + timedelta(seconds=settings.AI_LEASE_SECONDS) if lease_owner else None,
                          idempotency_key=idempotency_key, input_fingerprint=fingerprint))
            db.add(CreditTransaction(user_id=user_id, amount=-amount, type='reserve',
                                    reference_id=request_id, description=operation))
        return request_id

    def finish(self, request_id, *, success, latency_ms=0, error_code=None, lease_owner=None):
        with self.sessions.begin() as db:
            return self.finish_in_transaction(db, request_id, success=success,
                latency_ms=latency_ms, error_code=error_code, lease_owner=lease_owner)

    def finish_in_transaction(self, db, request_id, *, success, latency_ms=0, error_code=None, lease_owner=None):
        claimed = db.execute(update(AIUsage).execution_options(synchronize_session="fetch").where(AIUsage.id == request_id,
            AIUsage.record_kind == 'request', AIUsage.status == 'reserved',
            *([AIUsage.lease_owner == lease_owner, AIUsage.lease_expires_at > utcnow()] if lease_owner else []),
        ).values(status='success' if success else 'failed', latency_ms=latency_ms,
                 error_code=error_code))
        if not claimed.rowcount:
            return False
        request = db.get(AIUsage, request_id)
        calls = summarize_request(db, request)
        # Offline demo output incurs no charge. Provider failures still have
        # real upstream cost but an unsuccessful exam has zero user charge.
        charge = request.reserved_credits if success and calls else 0
        request.credits_charged = charge
        request.reserved_credits = 0
        reservation = db.scalar(select(CreditTransaction).where(
            CreditTransaction.user_id == request.user_id, CreditTransaction.reference_id == request_id,
            CreditTransaction.type == 'reserve'))
        refund = -reservation.amount - charge
        if refund:
            db.execute(update(UserSubscription).where(UserSubscription.user_id == request.user_id)
                       .values(credit_balance=UserSubscription.credit_balance + refund))
        db.add(CreditTransaction(user_id=request.user_id, amount=refund,
                                type='refund' if refund else 'settle', reference_id=request_id,
                                description=request.operation))
        return True

    def heartbeat(self, request_id, lease_owner):
        with self.sessions.begin() as db:
            return bool(db.execute(update(AIUsage).execution_options(synchronize_session="fetch").where(AIUsage.id == request_id,
                AIUsage.status == 'reserved', AIUsage.lease_owner == lease_owner,
                AIUsage.lease_expires_at > utcnow()).values(
                lease_expires_at=utcnow() + timedelta(seconds=settings.AI_LEASE_SECONDS))).rowcount)

    def adjust(self, user_id, *, amount=None, reset_to=None):
        """CLI-only adjustments; reset records a delta and preserves the ledger."""
        self.account(user_id)
        if (amount is None) == (reset_to is None):
            raise ValueError('Choose amount or reset_to')
        value = reset_to if reset_to is not None else amount
        if type(value) is not int or (reset_to is not None and value < 0):
            raise ValueError('Credits must be integers; reset balance must be nonnegative')
        with self.sessions.begin() as db:
            # Acquire the write lock before reading balance, also on SQLite.
            db.execute(update(UserSubscription).where(UserSubscription.user_id == user_id)
                       .values(credit_balance=UserSubscription.credit_balance))
            account = db.scalar(select(UserSubscription).where(UserSubscription.user_id == user_id))
            if reset_to is not None:
                pending = db.scalar(select(AIUsage.id).where(AIUsage.user_id == user_id, AIUsage.status == 'reserved'))
                if pending:
                    raise ValueError('Finish/recover pending requests before resetting credits')
            delta = reset_to - account.credit_balance if reset_to is not None else amount
            if account.credit_balance + delta < 0:
                raise AIError('INSUFFICIENT_CREDITS', 402)
            if account.credit_balance + delta + self.held(db, user_id) > MAX_CREDIT_BALANCE:
                raise ValueError('Credit balance including reservations exceeds supported limit')
            account.credit_balance += delta
            db.add(CreditTransaction(user_id=user_id, amount=delta, type='adjustment',
                reference_id=str(uuid4()), description='Development reset' if reset_to is not None else 'Development adjustment'))
        return self.account(user_id)

    def change_plan(self, user_id, plan):
        if plan not in PLAN_ALLOWANCES:
            raise ValueError('Unknown development plan')
        self.account(user_id)
        with self.sessions.begin() as db:
            db.execute(update(UserSubscription).where(UserSubscription.user_id == user_id)
                       .values(plan=plan, credit_allowance=PLAN_ALLOWANCES[plan], status='active',
                               settings_version=UserSubscription.settings_version + 1))
        # Changing plans does not mint credits repeatedly; reset/grant explicitly.
        return self.account(user_id)


class RequestReplay(Exception):
    def __init__(self, request_id):
        self.request_id = request_id
