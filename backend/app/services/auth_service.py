from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import InvalidTokenError as JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.services.rate_limit import ai_limiter
from app.services.role_policy import (
    KNOWN_ROLES,
    SCHOOL_ADMIN_ROLE,
    SUPER_ADMIN_ROLE,
    can_view_ai_provider_metadata,
    can_write_content,
    is_admin_role,
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    return pwd_context.hash("deka-dummy-password")

# HTTP Bearer scheme
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, role: str, token_version: int = 0, *, mfa_until: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "ver": token_version,
        "exp": expire,
    }
    if mfa_until is not None:
        payload["mfa_until"] = mfa_until
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], options={"require": ["exp", "sub"]})
    except JWTError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
        ) from error


def _user_id_from_payload(payload: dict) -> int:
    """Parse the untrusted JWT subject and fail closed on invalid values."""
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        user_id = 0
    if user_id <= 0:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")
    return user_id


def register_user(db: Session, email: str, password: str, name: str) -> User:
    existing = db.query(User).filter(User.email == email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email đã được đăng ký")

    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        name=name.strip(),
        role="teacher",
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = (
        db.query(User)
        .filter(User.email == email.lower().strip(), User.deleted_at.is_(None))
        .first()
    )
    candidate_hash = user.password_hash if user and user.password_hash else _dummy_password_hash()
    password_matches = verify_password(password, candidate_hash)
    if not user or not user.password_hash or not password_matches:
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Vui lòng xác minh email trước khi đăng nhập")
    return user


# ── FastAPI Dependencies ───────────────────────────────────

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    payload = decode_token(credentials.credentials)
    user_id = _user_id_from_payload(payload)
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Tài khoản không tồn tại hoặc đã bị khóa")
    if user.role not in KNOWN_ROLES:
        raise HTTPException(403, 'Vai trò không hợp lệ')
    if int(payload.get("ver", 0)) != int(user.token_version or 0):
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã bị thu hồi")
    if user.must_change_password and request.url.path not in {
        "/api/auth/me",
        "/api/auth/change-password",
        "/api/auth/logout",
    }:
        raise HTTPException(status_code=403, detail="Bạn phải đổi mật khẩu tạm trước khi tiếp tục")
    if settings.deployed and user.role == 'super_admin' and request.url.path not in {
        '/api/auth/me', '/api/auth/logout', '/api/auth/change-password',
        '/api/auth/mfa/status', '/api/auth/mfa/setup', '/api/auth/mfa/verify',
    }:
        import time
        if not isinstance(payload.get('mfa_until'), int) or payload['mfa_until'] <= time.time():
            raise HTTPException(403, {'code': 'ADMIN_MFA_REQUIRED', 'message': 'Xác thực MFA trong trang Tài khoản để tiếp tục quản trị (hiệu lực 10 phút).'})
    request.state.actor_role = user.role
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None instead of raising 401."""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        user_id = _user_id_from_payload(payload)
    except HTTPException:
        return None
    user = db.query(User).filter(
        User.id == user_id,
        User.is_active == True,
        User.deleted_at.is_(None),
    ).first()
    if not user or int(payload.get("ver", 0)) != int(user.token_version or 0):
        return None
    return user


def require_role(*roles: str):
    """Dependency factory: require the current user to have one of the given roles."""
    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Không có quyền truy cập")
        return user
    return _check


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require either platform-wide or school-scoped administrative access."""
    if not is_admin_role(user.role):
        raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền truy cập")
    return user


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    """Require the immutable platform administrator role."""
    if user.role != SUPER_ADMIN_ROLE:
        raise HTTPException(status_code=403, detail="Chỉ Super Admin mới có quyền truy cập")
    return user


def require_school_admin(user: User = Depends(get_current_user)) -> User:
    """Require a school administrator or the platform super administrator."""
    if user.role not in {SUPER_ADMIN_ROLE, SCHOOL_ADMIN_ROLE}:
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới có quyền truy cập")
    return user


def require_ai_metadata_viewer(user: User = Depends(get_current_user)) -> User:
    """Allow teaching roles to read safe provider metadata."""
    if not can_view_ai_provider_metadata(user.role):
        raise HTTPException(status_code=403, detail="Vai trò này không được xem metadata AI")
    return user


def require_ai_request(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    """Authenticate and rate-limit a costly AI action per user and route."""
    if not can_write_content(user.role):
        raise HTTPException(status_code=403, detail="Vai trò Viewer chỉ có quyền xem")
    ai_limiter.check(
        f"{user.id}:ai",
        limit=settings.AI_RATE_LIMIT_REQUESTS,
        window_seconds=settings.AI_RATE_LIMIT_WINDOW_SECONDS,
    )
    return user


def require_content_writer(user: User = Depends(get_current_user)) -> User:
    if not can_write_content(user.role):
        raise HTTPException(status_code=403, detail="Vai trò Viewer chỉ có quyền xem")
    return user
