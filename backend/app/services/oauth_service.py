"""OAuth service for Google and Facebook login."""
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User

# ── OAuth client setup ──────────────────────────────────
oauth = OAuth()

if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if settings.FACEBOOK_CLIENT_ID and settings.FACEBOOK_CLIENT_SECRET:
    oauth.register(
        name="facebook",
        client_id=settings.FACEBOOK_CLIENT_ID,
        client_secret=settings.FACEBOOK_CLIENT_SECRET,
        authorize_url="https://www.facebook.com/v18.0/dialog/oauth",
        access_token_url="https://graph.facebook.com/v18.0/oauth/access_token",
        client_kwargs={"scope": "email public_profile"},
    )


def find_or_create_oauth_user(
    db: Session,
    provider: str,
    oauth_id: str,
    email: str,
    email_verified: bool,
    name: str,
    avatar_url: str | None = None,
) -> User:
    """Resolve a provider identity without implicitly relinking by email."""
    if not provider or not oauth_id:
        raise HTTPException(status_code=400, detail="Nhà cung cấp OAuth không trả về định danh hợp lệ")
    # 1. Find by oauth_provider + oauth_id
    user = (
        db.query(User)
        .filter(
            User.oauth_provider == provider,
            User.oauth_id == oauth_id,
            User.deleted_at.is_(None),
        )
        .first()
    )
    if user:
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")
        # Update avatar if changed
        if avatar_url and user.avatar_url != avatar_url:
            user.avatar_url = avatar_url
            db.commit()
        return user

    normalized_email = email.lower().strip() if email else ""
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Nhà cung cấp OAuth không trả về email")
    if not email_verified:
        raise HTTPException(status_code=403, detail="Email OAuth chưa được nhà cung cấp xác minh")

    # Account linking must require an already-authenticated user in a dedicated
    # flow. Email equality alone must never replace a login method.
    if db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(
            status_code=409,
            detail="Email đã thuộc một tài khoản khác. Hãy đăng nhập bằng phương thức hiện có.",
        )

    # 3. Create new user
    user = User(
        email=normalized_email,
        password_hash=None,  # OAuth users don't have password
        name=name or "",
        role="teacher",
        is_active=True,
        email_verified=True,
        oauth_provider=provider,
        oauth_id=oauth_id,
        avatar_url=avatar_url,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        concurrent_identity = (
            db.query(User)
            .filter(User.oauth_provider == provider, User.oauth_id == oauth_id)
            .first()
        )
        if concurrent_identity:
            if not concurrent_identity.is_active:
                raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa") from error
            return concurrent_identity
        if db.query(User).filter(User.email == normalized_email).first():
            raise HTTPException(
                status_code=409,
                detail="Email đã thuộc một tài khoản khác. Hãy đăng nhập bằng phương thức hiện có.",
            ) from error
        raise
    db.refresh(user)
    return user


def get_google_client():
    """Get the Google OAuth client."""
    return oauth.create_client("google")


def get_facebook_client():
    """Get the Facebook OAuth client."""
    return oauth.create_client("facebook")
