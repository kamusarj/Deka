"""Audited production recovery. Dry-run by default; no public recovery endpoint."""
import argparse
import json
from sqlalchemy import select, update
from app.models.ai_account import AIUsage, UserSubscription
from app.models.user import User
from app.services.ai.credits import CreditService, utcnow
from app.services.audit_service import record_audit


def recover(credits, *, actor_id, apply=False, limit=100):
    if not 1 <= limit <= 1000:
        raise ValueError('Batch size must be between 1 and 1000')
    with credits.sessions() as db:
        actor = db.get(User, actor_id)
        if actor is None or actor.role != 'super_admin' or not actor.is_active or actor.deleted_at:
            raise ValueError('An active Super Admin actor is required')
        candidates = db.scalars(select(AIUsage.id).where(AIUsage.record_kind == 'request',
            AIUsage.status == 'reserved', AIUsage.lease_expires_at <= utcnow())
            .order_by(AIUsage.lease_expires_at).limit(limit)).all()
    changed = []
    for request_id in candidates:
        if not apply:
            changed.append(request_id)
            continue
        with credits.sessions.begin() as db:
            request = db.get(AIUsage, request_id)
            # Match worker commit lock ordering; a concurrent heartbeat can win.
            db.execute(update(User).where(User.id == request.user_id).values(token_version=User.token_version))
            db.execute(update(UserSubscription).where(UserSubscription.user_id == request.user_id)
                       .values(credit_balance=UserSubscription.credit_balance))
            claimed = db.execute(update(AIUsage).execution_options(synchronize_session="fetch").where(AIUsage.id == request_id,
                AIUsage.status == 'reserved', AIUsage.lease_expires_at <= utcnow())
                .values(lease_owner=None))
            if not claimed.rowcount:
                continue
            credits.finish_in_transaction(db, request_id, success=False, error_code='AI_WORKER_LOST')
            actor = db.get(User, actor_id)
            if actor is None or actor.role != 'super_admin' or not actor.is_active or actor.deleted_at:
                raise ValueError('Operator authority changed during recovery')
            record_audit(db, actor=actor, action='ai.request_recovered', target_type='ai_usage',
                         target_id=None, details={'request_id': request_id, 'policy': 'refund_expired_lease', 'upstream_outcome': 'unknown'})
            changed.append(request_id)
    return {'dry_run': not apply, 'request_ids': changed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actor-id', type=int, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(recover(CreditService(), actor_id=args.actor_id, apply=args.apply, limit=args.limit)))


if __name__ == '__main__':
    main()
