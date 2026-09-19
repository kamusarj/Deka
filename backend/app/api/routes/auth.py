from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, get_session_factory
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    EmailRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RegistrationResponse,
    ResetPasswordRequest,
    TokenRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.account_token_service import (
    RESET_PASSWORD,
    VERIFY_EMAIL,
    consume_account_token,
    issue_account_token,
)
from app.services.audit_service import record_audit
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    register_user,
    verify_password,
)
from app.services.email_service import send_account_email
from app.services.oauth_service import (
    find_or_create_oauth_user,
    get_facebook_client,
    get_google_client,
)
from app.services.rate_limit import login_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Email/Password Auth ──────────────────────────────────

def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_auth_rate_limit(action: str, request: Request, email: str) -> None:
    ip_address = _client_ip(request)
    limit_options = {
        "limit": settings.LOGIN_RATE_LIMIT_ATTEMPTS,
        "window_seconds": settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    }
    login_limiter.check(f"{action}:ip:{ip_address}", **limit_options)
    login_limiter.check(
        f"{action}:account:{email.lower().strip()}",
        **limit_options,
    )


@router.post("/register", response_model=RegistrationResponse, status_code=201)
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    _check_auth_rate_limit("register", request, str(body.email))
    if not settings.PUBLIC_REGISTRATION_ENABLED:
        raise HTTPException(503, 'Đăng ký đang tạm đóng')
    user = register_user(db, body.email, body.password, body.name)
    raw_token = issue_account_token(db, user.id, VERIFY_EMAIL)
    db.commit()
    try:
        send_account_email(
            recipient=user.email,
            subject="Xác minh tài khoản Smart Exam AI",
            text="Mở liên kết sau để xác minh email của bạn:",
            action_url=f"{settings.FRONTEND_URL}/#/verify-email?token={raw_token}",
        )
    except HTTPException as error:
        if error.status_code != 503:
            raise
        return RegistrationResponse(email_delivery_pending=True, message='Tài khoản đã được tạo nhưng chưa gửi được email. Vui lòng dùng Gửi lại email xác minh sau ít phút.')
    return RegistrationResponse()


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(body: TokenRequest, db: Session = Depends(get_db)):
    account_token = consume_account_token(db, body.token, VERIFY_EMAIL)
    user = db.query(User).filter(User.id == account_token.user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Liên kết không hợp lệ hoặc đã hết hạn")
    user.email_verified = True
    record_audit(db, actor=user, action="account.email_verified", target_type="user", target_id=user.id)
    db.commit()
    return MessageResponse(message="Email đã được xác minh. Bạn có thể đăng nhập.")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(request: Request, body: EmailRequest, db: Session = Depends(get_db)):
    _check_auth_rate_limit("resend-verification", request, str(body.email))
    user = db.query(User).filter(
        User.email == str(body.email).lower().strip(),
        User.deleted_at.is_(None),
    ).first()
    if user and user.is_active and not user.email_verified:
        raw_token = issue_account_token(db, user.id, VERIFY_EMAIL)
        db.commit()
        send_account_email(
            recipient=user.email,
            subject="Xác minh tài khoản Smart Exam AI",
            text="Mở liên kết sau để xác minh email của bạn:",
            action_url=f"{settings.FRONTEND_URL}/#/verify-email?token={raw_token}",
        )
    return MessageResponse(message="Nếu tài khoản cần xác minh, email hướng dẫn đã được gửi.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(request: Request, body: EmailRequest, db: Session = Depends(get_db)):
    _check_auth_rate_limit("forgot-password", request, str(body.email))
    user = db.query(User).filter(
        User.email == str(body.email).lower().strip(),
        User.deleted_at.is_(None),
    ).first()
    if user and user.is_active and user.password_hash:
        raw_token = issue_account_token(db, user.id, RESET_PASSWORD)
        db.commit()
        send_account_email(
            recipient=user.email,
            subject="Đặt lại mật khẩu Smart Exam AI",
            text="Mở liên kết sau để đặt lại mật khẩu:",
            action_url=f"{settings.FRONTEND_URL}/#/reset-password?token={raw_token}",
        )
    return MessageResponse(message="Nếu email tồn tại, hướng dẫn đặt lại mật khẩu đã được gửi.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    account_token = consume_account_token(db, body.token, RESET_PASSWORD)
    user = db.query(User).filter(User.id == account_token.user_id, User.deleted_at.is_(None)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Liên kết không hợp lệ hoặc đã hết hạn")
    if user.password_hash and verify_password(body.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải khác mật khẩu hiện tại")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.email_verified = True
    user.token_version = int(user.token_version or 0) + 1
    record_audit(db, actor=user, action="account.password_reset", target_type="user", target_id=user.id)
    db.commit()
    return MessageResponse(message="Mật khẩu đã được đặt lại. Bạn có thể đăng nhập.")


@router.post("/login", response_model=TokenResponse)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    _check_auth_rate_limit("login", request, body.email)
    user = authenticate_user(db, body.email, body.password)
    token = create_access_token(user.id, user.role, user.token_version)
    return TokenResponse(access_token=token, user=_to_user_response(user))


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return _to_user_response(user)


@router.post("/logout", status_code=204)
def logout(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.token_version = int(user.token_version or 0) + 1
    db.commit()


@router.put("/profile", response_model=UserResponse)
def update_profile(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.name is not None:
        normalized_name = body.name.strip()
        if not normalized_name:
            raise HTTPException(status_code=400, detail="Họ và tên không được để trống")
        user.name = normalized_name
    db.commit()
    db.refresh(user)
    return _to_user_response(user)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="Tài khoản OAuth không thể đổi mật khẩu")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải khác mật khẩu hiện tại")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    replacement_token = create_access_token(user.id, user.role, user.token_version)
    return {
        "message": "Đổi mật khẩu thành công",
        "access_token": replacement_token,
        "token_type": "bearer",
    }


# ── OAuth: Google ────────────────────────────────────────

@router.get("/login/google")
async def login_google(request: Request):
    """Redirect to Google OAuth consent screen."""
    client = get_google_client()
    if not client:
        raise HTTPException(status_code=503, detail="Google OAuth chưa được cấu hình")
    # Build the callback from the public request origin. The reverse proxy must
    # preserve the original Host header, including any non-default port.
    backend_redirect = request.url_for("callback_google")
    return await client.authorize_redirect(request, backend_redirect)


@router.get("/callback/google")
async def callback_google(request: Request):
    """Handle Google OAuth callback."""
    client = get_google_client()
    if not client:
        raise HTTPException(status_code=503, detail="Google OAuth chưa được cấu hình")

    token = await client.authorize_access_token(request)
    userinfo = token.get("userinfo", {})

    with get_session_factory()() as db:
        user = find_or_create_oauth_user(
            db=db,
            provider="google",
            oauth_id=userinfo.get("sub", ""),
            email=userinfo.get("email", ""),
            email_verified=userinfo.get("email_verified") is True,
            name=userinfo.get("name", ""),
            avatar_url=userinfo.get("picture"),
        )

    jwt_token = create_access_token(user.id, user.role, user.token_version)
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/#/auth/callback?token={jwt_token}")


# ── OAuth: Facebook ──────────────────────────────────────

@router.get("/login/facebook")
async def login_facebook(request: Request):
    """Redirect to Facebook OAuth consent screen."""
    client = get_facebook_client()
    if not client:
        raise HTTPException(status_code=503, detail="Facebook OAuth chưa được cấu hình")
    backend_redirect = request.url_for("callback_facebook")
    return await client.authorize_redirect(request, backend_redirect)


@router.get("/callback/facebook")
async def callback_facebook(request: Request):
    """Handle Facebook OAuth callback."""
    client = get_facebook_client()
    if not client:
        raise HTTPException(status_code=503, detail="Facebook OAuth chưa được cấu hình")

    token = await client.authorize_access_token(request)
    resp = await client.get("https://graph.facebook.com/me?fields=id,name,email,picture", token=token)
    userinfo = resp.json()

    picture_url = None
    if "picture" in userinfo and "data" in userinfo["picture"]:
        picture_url = userinfo["picture"]["data"].get("url")

    with get_session_factory()() as db:
        user = find_or_create_oauth_user(
            db=db,
            provider="facebook",
            oauth_id=userinfo.get("id", ""),
            email=userinfo.get("email", ""),
            # Facebook Graph supplies the app-authorized account email directly;
            # unlike Google it has no OIDC email_verified claim.
            email_verified=bool(userinfo.get("email")),
            name=userinfo.get("name", ""),
            avatar_url=picture_url,
        )

    jwt_token = create_access_token(user.id, user.role, user.token_version)
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/#/auth/callback?token={jwt_token}")


# ── OAuth: Config check ─────────────────────────────────

@router.get("/oauth-config")
def get_oauth_config():
    """Return which OAuth providers are configured (no secrets exposed)."""
    return {
        "google": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
        "facebook": bool(settings.FACEBOOK_CLIENT_ID and settings.FACEBOOK_CLIENT_SECRET),
    }


# ── Helpers ──────────────────────────────────────────────

def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        school_id=user.school_id,
        avatar_url=user.avatar_url,
        created_at=str(user.created_at) if user.created_at else None,
        can_change_password=bool(user.password_hash),
        email_verified=bool(user.email_verified),
        must_change_password=bool(user.must_change_password),
    )
