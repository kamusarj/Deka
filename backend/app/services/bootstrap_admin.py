"""Provision the first verified operator account from a restricted shell, without logging a password."""
import argparse
import getpass
import json
import os
from sqlalchemy import select, func, text
from app.core.database import get_session_factory
from app.models.user import User
from app.services.auth_service import hash_password
from app.services.audit_service import record_audit


def create(sessions, *, email, password, apply=False):
    from app.schemas.auth import RegisterRequest
    valid = RegisterRequest(email=email, password=password, name='Administrator')
    if not 12 <= len(password.encode('utf-8')) <= 72:
        raise ValueError('Administrator password must contain 12 to 72 UTF-8 bytes')
    with sessions.begin() as db:
        if db.bind.dialect.name == 'postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(184001)'))
        elif db.bind.dialect.name == 'sqlite':
            db.execute(text('UPDATE users SET id = id WHERE 1 = 0'))
        if db.scalar(select(func.count()).select_from(User).where(User.role == 'super_admin', User.deleted_at.is_(None))):
            raise ValueError('An administrator already exists; use authenticated administration')
        if db.scalar(select(User).where(User.email == str(valid.email).lower())):
            raise ValueError('Email already belongs to an account')
        if apply:
            user = User(email=str(valid.email).lower(), name='Administrator', role='super_admin',
                        email_verified=True, password_hash=hash_password(valid.password))
            db.add(user)
            db.flush()
            record_audit(db, actor=user, action='system.first_admin_provisioned', target_type='user', target_id=user.id)
    return {'dry_run': not apply, 'created': apply, 'next_step': 'Sign in and enroll MFA before administration'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True, help='Operator-controlled email verified out of band')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD') or getpass.getpass('Initial administrator password: ')
    try:
        print(json.dumps(create(get_session_factory(), email=args.email, password=password, apply=args.apply)))
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
        raise SystemExit(2)
