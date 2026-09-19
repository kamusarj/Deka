"""Persist actual provider attempts; request summaries own credit charges."""
import logging
from dataclasses import asdict
from uuid import uuid4
from sqlalchemy import select, update
from app.models.ai_account import AIUsage
from app.services.ai.pricing import AICostCalculator
from app.services.ai.errors import AccountingError

logger = logging.getLogger('app.ai')


def summarize_request(db, request):
    calls = db.scalars(select(AIUsage).where(AIUsage.request_id == request.id,
                                           AIUsage.record_kind == 'provider')).all()
    for field in ('input_tokens', 'output_tokens', 'cached_tokens', 'estimated_cost_usd'):
        values = [getattr(call, field) for call in calls]
        setattr(request, field, sum(values) if values and all(v is not None for v in values) else None)
    for field in ('provider', 'model'):
        values = {getattr(call, field) for call in calls}
        setattr(request, field, next(iter(values)) if len(values) == 1 else 'multiple' if values else None)
    return calls

class UsageRecorder:
    def __init__(self, session_factory, user_id, request_id, operation):
        self.sessions = session_factory
        self.user_id = user_id
        self.request_id = request_id
        self.operation = operation
        self.failed = False

    def __call__(self, response, error, operation=None):
        cost = AICostCalculator().calculate(response.provider, response.model, response.usage)
        fields = dict(user_id=self.user_id, request_id=self.request_id,
            provider=response.provider, model=response.model, operation=operation or self.operation,
            latency_ms=response.latency_ms, **asdict(response.usage),
            estimated_cost_usd=cost, status='failed' if error else 'success',
            error_code=error.code if error else None)
        try:
            with self.sessions.begin() as db:
                # Serialize summary updates/finalization; a late worker may add
                # actual cost but can never settle a refunded request.
                db.execute(update(AIUsage).where(AIUsage.id == self.request_id)
                           .values(status=AIUsage.status))
                request = db.get(AIUsage, self.request_id)
                if request.status != 'reserved':
                    fields['status'] = 'late_' + fields['status']
                db.add(AIUsage(id=str(uuid4()), record_kind='provider',
                               provider_request_id=response.request_id, **fields))
                db.flush()
                summarize_request(db, request)
        except Exception:
            self.failed = True
            raise AccountingError('AI usage storage failed') from None
        logger.info('ai_usage %s', ' '.join(f'{key}={value}' for key, value in fields.items()))
