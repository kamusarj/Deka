"""Administrative routes for schools, users, and role assignment."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.bank_question import BankQuestion
from app.models.document import UploadedDocument
from app.models.exam import Exam
from app.models.school import School
from app.models.user import User
from app.schemas.auth import UserResponse
from app.services.audit_service import record_audit
from app.services.auth_service import (
    get_current_user,
    hash_password,
    require_school_admin,
    require_super_admin,
)
from app.services.role_policy import SUPER_ADMIN_ROLE, TEACHER_ROLE, is_teacher_role

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Schemas ──────────────────────────────────────────────

class CreateSchoolRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    address: str | None = None
    phone: str | None = None


class SchoolResponse(BaseModel):
    id: int
    name: str
    address: str | None
    phone: str | None
    created_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CreateTeacherRequest(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    name: str = Field("", max_length=255)
    password: str = Field(..., min_length=6, max_length=128)


class UpdateTeacherRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class AssignExistingTeacherRequest(BaseModel):
    email: EmailStr


class UpdateUserRoleRequest(BaseModel):
    role: Literal["school_admin", "teacher", "viewer"]


class UpdateManagedUserRequest(BaseModel):
    name: str | None = Field(None, max_length=255)
    role: Literal["school_admin", "teacher", "viewer"] | None = None
    school_id: int | None = None
    is_active: bool | None = None


class CreateManagedUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field("", max_length=255)
    role: Literal["school_admin", "teacher", "viewer"] = "teacher"
    school_id: int | None = None


class UpdateSchoolRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    address: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=50)


class ResetManagedPasswordRequest(BaseModel):
    temporary_password: str = Field(..., min_length=6, max_length=128)


class TransferTeacherRequest(BaseModel):
    school_id: int | None = None


class AuditLogResponse(BaseModel):
    id: int
    actor_user_id: int | None
    action: str
    target_type: str
    target_id: int | None
    school_id: int | None
    details: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogPage(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


# ── Helpers ──────────────────────────────────────────────

def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        school_id=user.school_id,
        created_at=str(user.created_at) if user.created_at else None,
        can_change_password=bool(user.password_hash),
        email_verified=bool(user.email_verified),
        must_change_password=bool(user.must_change_password),
    )


def _to_school_response(school: School) -> SchoolResponse:
    return SchoolResponse(
        id=school.id,
        name=school.name,
        address=school.address,
        phone=school.phone,
        created_at=str(school.created_at) if school.created_at else None,
    )


# ── School Management ────────────────────────────────────

@router.get("/schools", response_model=list[SchoolResponse])
def list_schools(
    _admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """List every school for platform administration."""
    schools = db.query(School).order_by(School.name.asc(), School.id.asc()).all()
    return [_to_school_response(school) for school in schools]

@router.get("/users", response_model=list[UserResponse])
def list_users(
    _admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """List accounts for platform-level role administration."""
    users = db.query(User).filter(User.deleted_at.is_(None)).order_by(User.created_at.desc(), User.id.desc()).all()
    return [_to_user_response(user) for user in users]


@router.post("/users", response_model=UserResponse)
def create_managed_user(
    body: CreateManagedUserRequest,
    _admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Create a non-super-admin account anywhere on the platform."""
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email đã được đăng ký")
    if body.school_id is not None and db.get(School, body.school_id) is None:
        raise HTTPException(status_code=400, detail="Trường được chọn không tồn tại")
    if body.role == "school_admin" and body.school_id is None:
        raise HTTPException(status_code=400, detail="School Admin phải thuộc một trường")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        name=body.name.strip(),
        role=body.role,
        school_id=body.school_id,
        is_active=True,
        email_verified=True,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    record_audit(
        db, actor=_admin, action="admin.user_created", target_type="user",
        target_id=user.id, school_id=user.school_id, details={"role": user.role},
    )
    db.commit()
    db.refresh(user)
    return _to_user_response(user)


@router.put("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    body: UpdateUserRoleRequest,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Promote or demote a school administrator without exposing super-admin assignment."""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Super Admin không thể tự đổi vai trò")
    if target.role == SUPER_ADMIN_ROLE:
        raise HTTPException(status_code=403, detail="Không thể thay đổi Super Admin")
    if body.role == "school_admin" and target.school_id is None:
        raise HTTPException(
            status_code=400,
            detail="Tài khoản phải thuộc một trường trước khi được cấp quyền Admin",
        )

    target.role = body.role
    record_audit(
        db, actor=admin, action="admin.user_role_changed", target_type="user",
        target_id=target.id, school_id=target.school_id, details={"role": body.role},
    )
    db.commit()
    db.refresh(target)
    return _to_user_response(target)

@router.put("/users/{user_id}", response_model=UserResponse)
def update_managed_user(
    user_id: int,
    body: UpdateManagedUserRequest,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Update a non-super-admin account within the platform management boundary."""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    if target.role == SUPER_ADMIN_ROLE or target.id == admin.id:
        raise HTTPException(status_code=403, detail="Không thể thay đổi tài khoản Super Admin")

    requested_school_id = body.school_id if "school_id" in body.model_fields_set else target.school_id
    requested_role = body.role if body.role is not None else target.role
    if (
        target.role == TEACHER_ROLE
        and requested_role == TEACHER_ROLE
        and "school_id" in body.model_fields_set
        and requested_school_id != target.school_id
    ):
        raise HTTPException(
            status_code=409,
            detail="Hãy dùng thao tác chuyển trường rõ ràng cho Teacher",
        )
    if requested_school_id is not None and db.get(School, requested_school_id) is None:
        raise HTTPException(status_code=400, detail="Trường được chọn không tồn tại")

    if requested_role == "school_admin" and requested_school_id is None:
        raise HTTPException(status_code=400, detail="School Admin phải thuộc một trường")

    if body.name is not None:
        target.name = body.name.strip()
    if body.role is not None:
        target.role = body.role
    if "school_id" in body.model_fields_set:
        target.school_id = body.school_id
    if body.is_active is not None:
        target.is_active = body.is_active

    record_audit(
        db, actor=admin, action="admin.user_updated", target_type="user",
        target_id=target.id, school_id=target.school_id,
        details={"fields": sorted(body.model_fields_set)},
    )

    db.commit()
    db.refresh(target)
    return _to_user_response(target)


@router.post("/schools", response_model=SchoolResponse)
@router.post("/school", response_model=SchoolResponse)
def create_school(
    body: CreateSchoolRequest,
    _admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Create a school without implicitly changing any account membership."""
    school = School(name=body.name.strip(), address=body.address, phone=body.phone)
    db.add(school)
    db.flush()
    record_audit(db, actor=_admin, action="admin.school_created", target_type="school", target_id=school.id)
    db.commit()
    db.refresh(school)
    return _to_school_response(school)


@router.put("/schools/{school_id}", response_model=SchoolResponse)
def update_school(
    school_id: int,
    body: UpdateSchoolRequest,
    _admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Edit school metadata without deleting the school or its memberships."""
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="Không tìm thấy trường")
    if body.name is not None:
        school.name = body.name.strip()
    if "address" in body.model_fields_set:
        school.address = body.address.strip() if body.address else None
    if "phone" in body.model_fields_set:
        school.phone = body.phone.strip() if body.phone else None
    record_audit(
        db, actor=_admin, action="admin.school_updated", target_type="school",
        target_id=school.id, school_id=school.id, details={"fields": sorted(body.model_fields_set)},
    )
    db.commit()
    db.refresh(school)
    return _to_school_response(school)


@router.get("/school", response_model=SchoolResponse | None)
def get_my_school(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the school of the current user."""
    if not user.school_id:
        return None
    school = db.query(School).filter(School.id == user.school_id).first()
    if not school:
        return None
    return _to_school_response(school)


# ── Teacher Management ───────────────────────────────────

@router.get("/teachers", response_model=list[UserResponse])
def list_teachers(
    user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    """List all teachers in the school_admin's school."""
    if not user.school_id:
        raise HTTPException(status_code=400, detail="Bạn chưa thuộc trường nào")

    teachers = (
        db.query(User)
        .filter(
            User.school_id == user.school_id,
            User.role == TEACHER_ROLE,
            User.deleted_at.is_(None),
        )
        .order_by(User.created_at.desc())
        .all()
    )
    return [_to_user_response(t) for t in teachers]


@router.post("/teachers", response_model=UserResponse)
def create_teacher(
    body: CreateTeacherRequest,
    user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    """Create a new teacher account in the school_admin's school."""
    if not user.school_id:
        raise HTTPException(status_code=400, detail="Bạn chưa thuộc trường nào")

    # Check email uniqueness
    existing = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email đã được đăng ký")

    teacher = User(
        email=body.email.lower().strip(),
        password_hash=hash_password(body.password),
        name=body.name.strip(),
        role="teacher",
        is_active=True,
        school_id=user.school_id,
        email_verified=True,
        must_change_password=True,
    )
    db.add(teacher)
    db.flush()
    record_audit(
        db, actor=user, action="admin.teacher_created", target_type="user",
        target_id=teacher.id, school_id=teacher.school_id,
    )
    db.commit()
    db.refresh(teacher)
    return _to_user_response(teacher)


@router.post("/teachers/assign", response_model=UserResponse)
def assign_existing_teacher(
    body: AssignExistingTeacherRequest,
    user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    """Add an existing, currently unassigned teacher account to this school.

    An administrator cannot use this endpoint to take an account from another
    school or to change an administrator's role. Those operations require a
    separate, explicit transfer workflow.
    """
    if not user.school_id:
        raise HTTPException(status_code=400, detail="Bạn chưa thuộc trường nào")

    teacher = db.query(User).filter(
        User.email == body.email.lower().strip(), User.deleted_at.is_(None)
    ).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản với email này")
    if not is_teacher_role(teacher.role):
        raise HTTPException(status_code=400, detail="Chỉ có thể thêm tài khoản Teacher")
    if teacher.school_id == user.school_id:
        raise HTTPException(status_code=400, detail="Giáo viên này đã thuộc trường của bạn")
    if teacher.school_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Giáo viên này đang thuộc một trường khác. Không thể tự chuyển trường.",
        )

    teacher.school_id = user.school_id
    record_audit(
        db, actor=user, action="admin.teacher_assigned", target_type="user",
        target_id=teacher.id, school_id=user.school_id,
    )
    db.commit()
    db.refresh(teacher)
    return _to_user_response(teacher)


@router.put("/teachers/{teacher_id}", response_model=UserResponse)
def update_teacher(
    teacher_id: int,
    body: UpdateTeacherRequest,
    user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    """Update a teacher's info (name, is_active)."""
    if not user.school_id:
        raise HTTPException(status_code=400, detail="Bạn chưa thuộc trường nào")

    teacher = (
        db.query(User)
        .filter(
            User.id == teacher_id,
            User.school_id == user.school_id,
            User.role == TEACHER_ROLE,
            User.deleted_at.is_(None),
        )
        .first()
    )
    if not teacher:
        raise HTTPException(status_code=404, detail="Không tìm thấy giáo viên")

    if body.name is not None:
        teacher.name = body.name.strip()
    if body.is_active is not None:
        teacher.is_active = body.is_active

    record_audit(
        db, actor=user, action="admin.teacher_updated", target_type="user",
        target_id=teacher.id, school_id=teacher.school_id,
        details={"fields": sorted(body.model_fields_set)},
    )

    db.commit()
    db.refresh(teacher)
    return _to_user_response(teacher)


@router.delete("/teachers/{teacher_id}")
def delete_teacher(
    teacher_id: int,
    user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    """Remove a teacher from the school without deleting their account."""
    if not user.school_id:
        raise HTTPException(status_code=400, detail="Bạn chưa thuộc trường nào")

    teacher = (
        db.query(User)
        .filter(
            User.id == teacher_id,
            User.school_id == user.school_id,
            User.role == TEACHER_ROLE,
            User.deleted_at.is_(None),
        )
        .first()
    )
    if not teacher:
        raise HTTPException(status_code=404, detail="Không tìm thấy giáo viên")

    teacher.school_id = None
    record_audit(
        db, actor=user, action="admin.teacher_unassigned", target_type="user",
        target_id=teacher.id, school_id=user.school_id,
    )
    db.commit()
    return {"id": teacher_id, "removed": True}


@router.post("/users/{user_id}/reset-password")
def reset_managed_password(
    user_id: int,
    body: ResetManagedPasswordRequest,
    admin: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    if target.role == SUPER_ADMIN_ROLE or target.id == admin.id:
        raise HTTPException(status_code=403, detail="Không thể đặt lại mật khẩu tài khoản này")
    if admin.role != SUPER_ADMIN_ROLE and (
        target.school_id != admin.school_id or target.role != TEACHER_ROLE
    ):
        raise HTTPException(status_code=403, detail="Không có quyền quản lý tài khoản này")
    target.password_hash = hash_password(body.temporary_password)
    target.must_change_password = True
    target.email_verified = True
    target.token_version = int(target.token_version or 0) + 1
    record_audit(
        db, actor=admin, action="admin.password_reset", target_type="user",
        target_id=target.id, school_id=target.school_id,
    )
    db.commit()
    return {"message": "Đã đặt mật khẩu tạm. Người dùng phải đổi mật khẩu khi đăng nhập."}


@router.post("/teachers/{teacher_id}/transfer", response_model=UserResponse)
def transfer_teacher(
    teacher_id: int,
    body: TransferTeacherRequest,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    teacher = db.query(User).filter(
        User.id == teacher_id,
        User.role == TEACHER_ROLE,
        User.deleted_at.is_(None),
    ).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Không tìm thấy giáo viên")
    if body.school_id is not None and db.get(School, body.school_id) is None:
        raise HTTPException(status_code=400, detail="Trường đích không tồn tại")
    previous_school_id = teacher.school_id
    teacher.school_id = body.school_id
    record_audit(
        db, actor=admin, action="admin.teacher_transferred", target_type="user",
        target_id=teacher.id, school_id=body.school_id,
        details={"from_school_id": previous_school_id, "to_school_id": body.school_id},
    )
    db.commit()
    db.refresh(teacher)
    return _to_user_response(teacher)


@router.delete("/users/{user_id}")
def soft_delete_user(
    user_id: int,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    if target.id == admin.id or target.role == SUPER_ADMIN_ROLE:
        raise HTTPException(status_code=403, detail="Không thể xóa Super Admin")
    target.is_active = False
    target.deleted_at = datetime.now(timezone.utc)
    target.token_version = int(target.token_version or 0) + 1
    record_audit(
        db, actor=admin, action="admin.user_soft_deleted", target_type="user",
        target_id=target.id, school_id=target.school_id,
    )
    db.commit()
    return {"id": user_id, "deleted": True}


@router.delete("/schools/{school_id}")
def delete_school(
    school_id: int,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="Không tìm thấy trường")
    references = {
        "users": db.query(User).filter(User.school_id == school_id).count(),
        "exams": db.query(Exam).filter(Exam.school_id == school_id).count(),
        "documents": db.query(UploadedDocument).filter(UploadedDocument.school_id == school_id).count(),
        "bank_questions": db.query(BankQuestion).filter(BankQuestion.school_id == school_id).count(),
    }
    if any(references.values()):
        raise HTTPException(
            status_code=409,
            detail={"message": "Không thể xóa trường còn dữ liệu tham chiếu", "references": references},
        )
    record_audit(
        db, actor=admin, action="admin.school_deleted", target_type="school",
        target_id=school.id, school_id=school.id,
    )
    db.delete(school)
    db.commit()
    return {"id": school_id, "deleted": True}


@router.get("/audit-logs", response_model=AuditLogPage)
def list_audit_logs(
    action: str | None = None,
    target_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    admin: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    query = db.query(AuditLog)
    if admin.role != SUPER_ADMIN_ROLE:
        query = query.filter(AuditLog.school_id == admin.school_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)
    total = query.count()
    items = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return AuditLogPage(items=items, total=total, page=page, page_size=page_size)
