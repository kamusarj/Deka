"""Signed current authority snapshot, separate from old backups; conservative restore reconciliation."""
import argparse
import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, text
from app.core.config import settings
from app.core.database import get_session_factory
from app.models.user import User
from app.models.document import UploadedDocument
from app.models.ai_account import UserSubscription
from app.models.admin_mfa import AdminMFA
from app.services.audit_service import record_audit


def digest(value):
    key = settings.MFA_ENCRYPTION_KEY or settings.SECRET_KEY
    return hmac.new(key.encode(), ('restore-authority:' + value).encode(), hashlib.sha256).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def snapshot(sessions):
    with sessions.begin() as db:
        if db.bind.dialect.name == 'postgresql':
            db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        elif db.bind.dialect.name == 'sqlite':
            db.execute(text('BEGIN'))
        users = [{'id': u.id, 'identity': digest(u.email), 'credentials': digest(u.password_hash or ''),
                  'oauth': digest(canonical([u.oauth_provider, u.oauth_id])),
                  'role': u.role, 'school_id': u.school_id, 'is_active': u.is_active,
                  'email_verified': u.email_verified, 'token_version': u.token_version,
                  'deleted_at': u.deleted_at.isoformat() if u.deleted_at else None}
                 for u in db.scalars(select(User).order_by(User.id))]
        subscriptions = {str(s.user_id): s.status for s in db.scalars(select(UserSubscription))}
        mfa = {str(m.user_id): {'digest': digest(m.encrypted_secret), 'last_counter': m.last_counter,
                               'recovery_hashes': m.recovery_hashes, 'enabled': m.enabled}
               for m in db.scalars(select(AdminMFA))}
    data = {'version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'users': users, 'subscriptions': subscriptions, 'mfa': mfa}
    return {'data': data, 'signature': digest(canonical(data))}


def reconcile(sessions, envelope, *, actor_id, apply=False):
    data = envelope['data']
    if data.get('version') != 1 or not hmac.compare_digest(envelope['signature'], digest(canonical(data))):
        raise ValueError('Authority snapshot signature/version invalid')
    generated = datetime.fromisoformat(data['generated_at'])
    age = (datetime.now(timezone.utc) - generated).total_seconds()
    if not 0 <= age <= 86400:
        raise ValueError('Current authority snapshot must be refreshed within 24 hours')
    current = {u['id']: u for u in data['users']}
    if len(current) != len(data['users']):
        raise ValueError('Duplicate identity in snapshot')
    with sessions.begin() as db:
        actor = db.get(User, actor_id)
        proof = current.get(actor_id)
        if not actor or not proof or proof['role'] != 'super_admin' or not proof['is_active'] or proof['deleted_at'] or proof['identity'] != digest(actor.email):
            raise ValueError('Current active Super Admin required')
        locked, password_resets, count = [], [], 0
        for user in db.scalars(select(User).order_by(User.id).with_for_update()):
            row = current.get(user.id)
            count += 1
            if not row or row['identity'] != digest(user.email) or row['oauth'] != digest(canonical([user.oauth_provider, user.oauth_id])):
                locked.append(user.id)
                if apply:
                    user.is_active = False
                    user.token_version += 1
                continue
            if apply:
                user.role, user.school_id = row['role'], row['school_id']
                user.is_active, user.email_verified = row['is_active'], row['email_verified']
                user.deleted_at = datetime.fromisoformat(row['deleted_at']) if row['deleted_at'] else None
                user.token_version = max(user.token_version, row['token_version']) + 1
                subscription = db.scalar(select(UserSubscription).where(UserSubscription.user_id == user.id))
                if subscription:
                    subscription.status = data['subscriptions'].get(str(user.id), 'paused')
            if row['credentials'] != digest(user.password_hash or ''):
                password_resets.append(user.id)
                if apply:
                    user.password_hash = None
                    user.must_change_password = True
            state, latest = db.get(AdminMFA, user.id), data['mfa'].get(str(user.id))
            if latest and latest['enabled'] and (state is None or digest(state.encrypted_secret) != latest['digest']):
                locked.append(user.id)
                if apply:
                    user.is_active = False
            elif apply and state:
                if not latest or not latest['enabled']:
                    db.delete(state)
                else:
                    state.enabled = True
                    state.last_counter = max(state.last_counter, latest['last_counter'])
                    state.recovery_hashes = [x for x in state.recovery_hashes if x in latest['recovery_hashes']]
        # Never resurrect a sharing grant. Owners can deliberately re-share after recovery.
        documents = db.scalars(select(UploadedDocument).where(UploadedDocument.sharing_scope != 'private')).all()
        if apply:
            for document in documents:
                document.sharing_scope, document.sharing_status = 'private', 'none'
            record_audit(db, actor=actor, action='system.restore_authority_reconciled', target_type='user',
                         details={'users': count, 'quarantined': locked, 'password_resets': password_resets,
                                  'shares_revoked': len(documents)})
        return {'dry_run': not apply, 'users': count, 'quarantined': locked,
                'password_resets': password_resets, 'shares_revoked': len(documents)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['export', 'reconcile'])
    parser.add_argument('--journal')
    parser.add_argument('--actor-id', type=int)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.command == 'export':
        result = snapshot(get_session_factory())
    else:
        if not args.journal or not args.actor_id:
            parser.error('reconcile requires --journal and --actor-id')
        result = reconcile(get_session_factory(), json.loads(Path(args.journal).read_text()), actor_id=args.actor_id, apply=args.apply)
    print(json.dumps(result))

if __name__ == '__main__':
    main()
