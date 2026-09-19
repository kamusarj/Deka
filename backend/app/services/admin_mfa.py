"""RFC 6238 TOTP with encrypted secrets, replay fencing and one-use recovery."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import update
from app.core.config import settings
from app.models.admin_mfa import AdminMFA
from app.models.user import User
from app.services.audit_service import record_audit


def cipher(key=None):
    material = key or settings.MFA_ENCRYPTION_KEY or settings.SECRET_KEY
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('admin-mfa:' + material).encode()).digest()))


def totp(secret, counter):
    digest = hmac.new(base64.b32decode(secret), struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return f'{(struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff) % 1000000:06d}'


def setup(db, actor):
    db.execute(update(User).where(User.id == actor.id).values(token_version=User.token_version))
    existing = db.get(AdminMFA, actor.id, populate_existing=True)
    if existing and existing.enabled:
        raise HTTPException(409, 'MFA đã được kích hoạt')
    secret = base64.b32encode(secrets.token_bytes(20)).decode()
    if existing:
        existing.encrypted_secret = cipher().encrypt(secret.encode()).decode()
        existing.last_counter = -1
    else:
        db.add(AdminMFA(user_id=actor.id, encrypted_secret=cipher().encrypt(secret.encode()).decode(), recovery_hashes=[]))
    record_audit(db, actor=actor, action='account.mfa_setup', target_type='user', target_id=actor.id)
    db.commit()
    return {'secret': secret, 'uri': f'otpauth://totp/{quote("Smart Exam:" + actor.email)}?secret={secret}&issuer=Smart%20Exam&algorithm=SHA1&digits=6&period=30'}


def verify(db, actor, code):
    db.execute(update(User).where(User.id == actor.id).values(token_version=User.token_version))
    state = db.get(AdminMFA, actor.id, populate_existing=True)
    if state is None:
        raise HTTPException(409, 'Hãy thiết lập MFA trước')
    counter = int(time.time() // 30)
    secret = cipher().decrypt(state.encrypted_secret.encode()).decode()
    matched = next((step for step in (counter, counter - 1, counter + 1)
                    if step > state.last_counter and hmac.compare_digest(totp(secret, step), code)), None)
    recovery = hashlib.sha256(code.encode()).hexdigest()
    if matched is None:
        if not state.enabled or recovery not in state.recovery_hashes:
            raise HTTPException(400, 'Mã MFA không hợp lệ hoặc đã sử dụng')
        state.recovery_hashes = [item for item in state.recovery_hashes if item != recovery]
    else:
        state.last_counter = matched
    codes = []
    if not state.enabled:
        codes = [secrets.token_hex(12) for _ in range(10)]
        state.recovery_hashes = [hashlib.sha256(item.encode()).hexdigest() for item in codes]
        state.enabled = True
    record_audit(db, actor=actor, action='account.mfa_verified', target_type='user', target_id=actor.id,
                 details={'recovery_code': matched is None})
    db.commit()
    return codes
