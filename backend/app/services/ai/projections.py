"""Allowlisted public accounting fields. ORM schema changes never widen responses."""
from app.services.ai.credits import utcnow

SUBSCRIPTION_FIELDS = ('id', 'user_id', 'plan', 'status', 'settings_version',
    'credit_allowance', 'credit_balance', 'current_period_start', 'current_period_end',
    'created_at', 'updated_at')
LEDGER_FIELDS = ('id', 'amount', 'type', 'reference_id', 'created_at')
USAGE_FIELDS = ('id', 'request_id', 'operation', 'record_kind', 'status',
    'credits_charged', 'reserved_credits', 'created_at', 'error_code', 'result_exam_id', 'result_version')
PROVIDER_FIELDS = ('provider', 'model', 'provider_request_id', 'input_tokens',
    'output_tokens', 'cached_tokens', 'estimated_cost_usd', 'latency_ms')
METRIC_FIELDS = ('requests', 'success', 'failed', 'pending', 'credits_charged',
    'reserved_credits', 'provider_calls', 'active_users', 'day', 'role',
    'id', 'name', 'email', 'is_active', 'plan', 'credit_balance')
ADMIN_METRIC_FIELDS = ('input_tokens', 'output_tokens', 'unknown_token_calls',
    'known_cost_usd', 'estimated_cost_usd', 'unpriced_calls')


def fields(row, names):
    return {name: getattr(row, name) for name in names}


def subscription_projection(row):
    if row is None:
        return None
    data = fields(row, SUBSCRIPTION_FIELDS)
    end = row.current_period_end
    data['renewal_due'] = end.replace(tzinfo=utcnow().tzinfo) <= utcnow()
    return data


def usage_projection(row, actor):
    return fields(row, USAGE_FIELDS + (PROVIDER_FIELDS if actor.role == 'super_admin' else ()))


def metrics_projection(data, actor):
    allowed = METRIC_FIELDS + (ADMIN_METRIC_FIELDS if actor.role == 'super_admin' else ())
    return {name: data[name] for name in allowed if name in data}
