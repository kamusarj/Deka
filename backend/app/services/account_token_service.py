import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.account_token import AccountToken

VERIFY_EMAIL = "verify_email"
RESET_PASSWORD = "reset_password"


def _digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_account_token(db: Session, user_id: int, purpose: str) -> str:
    now = datetime.now(timezone.utc)
    (
        db.query(AccountToken)
        .filter(
            AccountToken.user_id == user_id,
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
        )
        .update({AccountToken.used_at: now}, synchronize_session=False)
    )
    raw_token = secrets.token_urlsafe(32)
    db.add(
        AccountToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=_digest(raw_token),
            expires_at=now + timedelta(minutes=settings.ACCOUNT_TOKEN_EXPIRE_MINUTES),
        )
    )
    return raw_token


def consume_account_token(db: Session, raw_token: str, purpose: str) -> AccountToken:
    now = datetime.now(timezone.utc)
    token_hash = _digest(raw_token)
    # Claim eligibility in one SQL write. Two requests may read the same unused
    # row, but only one may change it; the account mutation/audit shares this
    # transaction, so a failure rolls back the claim as well.
    claimed = (
        db.query(AccountToken)
        .filter(
            AccountToken.token_hash == token_hash,
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
            AccountToken.expires_at > now,
        )
        .update({AccountToken.used_at: now}, synchronize_session=False)
    )
    if claimed != 1:
        raise HTTPException(status_code=400, detail="Liên kết không hợp lệ hoặc đã hết hạn")
    return db.query(AccountToken).filter(AccountToken.token_hash == token_hash).populate_existing().one()
