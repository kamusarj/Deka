"""Read-only operator health summary, suitable for timer/monitor exit-code alerts."""
import json
import shutil
from sqlalchemy import select, func
from app.core.config import settings
from app.core.database import get_session_factory
from app.models.ai_account import AIUsage
from app.models.document_cleanup import DocumentCleanup
from app.services.ai.credits import utcnow


def snapshot():
    sessions = get_session_factory()
    with sessions() as db:
        overdue = db.scalar(select(func.count()).select_from(AIUsage).where(
            AIUsage.record_kind == 'request', AIUsage.status == 'reserved', AIUsage.lease_expires_at <= utcnow()))
        unleased = db.scalar(select(func.count()).select_from(AIUsage).where(
            AIUsage.record_kind == 'request', AIUsage.status == 'reserved', AIUsage.lease_expires_at.is_(None)))
        cleanup = db.scalar(select(func.count()).select_from(DocumentCleanup).where(DocumentCleanup.status != 'complete'))
        day = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        unknown = db.scalar(select(func.count()).select_from(AIUsage).where(AIUsage.record_kind == 'provider',
            AIUsage.created_at >= day, AIUsage.estimated_cost_usd.is_(None)))
    free = shutil.disk_usage('.').free
    return {'expired_leases': overdue, 'legacy_unleased_requests': unleased, 'pending_cleanup': cleanup,
            'unpriced_attempts_today': unknown, 'free_bytes': free,
            'needs_attention': bool(overdue or unleased or cleanup or unknown or free < 2 * 1024**3)}


if __name__ == '__main__':
    try:
        result = snapshot()
    except Exception as error:
        print(json.dumps({'status': 'unavailable', 'error_type': type(error).__name__}))
        raise SystemExit(2)
    print(json.dumps(result))
    raise SystemExit(1 if result['needs_attention'] else 0)
