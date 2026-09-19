import time
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.admin_mfa import AdminMFA
from app.models.user import User
from app.services.auth_service import get_current_user, verify_password, create_access_token
from app.services import admin_mfa
from app.api.routes.auth import _check_auth_rate_limit

router = APIRouter(prefix='/auth/mfa', tags=['auth'])


class MFAProof(BaseModel):
    model_config = ConfigDict(extra='forbid')
    password: str = Field(min_length=1, max_length=72)
    code: str = Field(default='', max_length=32)


def proof(request, body, actor):
    if actor.role != 'super_admin':
        raise HTTPException(403, 'Chỉ Super Admin được thiết lập MFA quản trị')
    _check_auth_rate_limit('mfa', request, actor.email)
    if not actor.password_hash or not verify_password(body.password, actor.password_hash):
        raise HTTPException(403, 'Cần xác thực lại bằng mật khẩu tài khoản')


@router.get('/status')
def status(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if actor.role != 'super_admin':
        raise HTTPException(403, 'Không có quyền')
    state = db.get(AdminMFA, actor.id)
    return {'enabled': bool(state and state.enabled)}


@router.post('/setup')
def setup(request: Request, body: MFAProof, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proof(request, body, actor)
    return admin_mfa.setup(db, actor)


@router.post('/verify')
def verify(request: Request, body: MFAProof, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proof(request, body, actor)
    codes = admin_mfa.verify(db, actor, body.code.strip())
    return {'access_token': create_access_token(actor.id, actor.role, actor.token_version,
              mfa_until=int(time.time()) + 600), 'recovery_codes': codes, 'valid_seconds': 600}
