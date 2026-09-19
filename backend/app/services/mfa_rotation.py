"""Operator-only transactional MFA re-encryption; keys are read from environment, never argv/logs."""
import argparse
import os
from sqlalchemy import select
from app.core.database import get_session_factory
from app.models.admin_mfa import AdminMFA
from app.models.user import User
from app.services.admin_mfa import cipher
from app.services.audit_service import record_audit


def rotate(sessions, *, actor_id, old_key, new_key, apply=False):
    if min(len(old_key), len(new_key)) < 32 or old_key == new_key:
        raise ValueError('Distinct strong old/new keys are required')
    with sessions.begin() as db:
        actor = db.scalar(select(User).where(User.id == actor_id).with_for_update())
        if not actor or actor.role != 'super_admin' or not actor.is_active or actor.deleted_at:
            raise ValueError('Active Super Admin required')
        states = db.scalars(select(AdminMFA).order_by(AdminMFA.user_id).with_for_update()).all()
        for state in states:
            plain = cipher(old_key).decrypt(state.encrypted_secret.encode())
            if apply:
                state.encrypted_secret = cipher(new_key).encrypt(plain).decode()
        if apply:
            record_audit(db, actor=actor, action='account.mfa_keys_rotated', target_type='admin_mfa', details={'count': len(states)})
        return {'dry_run': not apply, 'count': len(states)}


def main():
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actor-id', required=True, type=int)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        result = rotate(get_session_factory(), actor_id=args.actor_id,
            old_key=os.environ['MFA_ROTATION_OLD_KEY'], new_key=os.environ['MFA_ROTATION_NEW_KEY'], apply=args.apply)
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
        raise SystemExit(2)
    print(json.dumps(result))

if __name__ == '__main__':
    main()
