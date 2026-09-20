"""Explicit local/demo account provisioning; never called during app startup."""

import argparse

from sqlalchemy.orm import Session

from app.core.database import get_session_factory
from app.models.school import School
from app.models.user import User
from app.services.audit_service import record_audit
from app.services.auth_service import hash_password, verify_password

DEMO_PASSWORD = "Demo@123456"
DEMO_SCHOOL_NAME = "Trường THCS Demo"
DEMO_ACCOUNTS = (
    ("super_admin", "superadmin@demo.deka.test", "Demo · Quản trị hệ thống"),
    ("school_admin", "schooladmin@demo.deka.test", "Demo · Quản trị trường"),
    ("teacher", "teacher@demo.deka.test", "Demo · Giáo viên"),
    ("viewer", "viewer@demo.deka.test", "Demo · Người xem"),
)


def seed_demo_accounts(db: Session) -> list[dict[str, str]]:
    """Stage demo records in the caller's transaction, refusing account resets."""
    school = db.query(School).filter(School.name == DEMO_SCHOOL_NAME).one_or_none()
    existing = {
        user.email: user
        for user in db.query(User).filter(
            User.email.in_([email for _, email, _ in DEMO_ACCOUNTS])
        ).all()
    }
    # Check every reserved address before staging any writes.
    for role, email, _ in DEMO_ACCOUNTS:
        user = existing.get(email)
        if user is None:
            continue
        expected_school_id = None if role == "super_admin" or school is None else school.id
        if (
            user.role != role
            or user.school_id != expected_school_id
            or (role != "super_admin" and school is None)
            or not user.is_active
            or not user.email_verified
            or user.must_change_password
            or user.deleted_at is not None
            or user.oauth_provider is not None
            or not user.password_hash
            or not verify_password(DEMO_PASSWORD, user.password_hash)
        ):
            raise ValueError(f"Demo email conflicts with an existing account: {email}; no accounts changed")

    if school is None:
        school = School(name=DEMO_SCHOOL_NAME, address="Trường mẫu để thử các vai trò")
        db.add(school)
        db.flush()
        record_audit(
            db, actor=None, action="demo.school_created", target_type="school",
            target_id=school.id, school_id=school.id,
        )

    result = []
    for role, email, name in DEMO_ACCOUNTS:
        if email in existing:
            result.append({"role": role, "email": email, "status": "reused"})
            continue
        user = User(
            email=email, name=name, role=role,
            password_hash=hash_password(DEMO_PASSWORD),
            school_id=None if role == "super_admin" else school.id,
            is_active=True, email_verified=True, must_change_password=False,
        )
        db.add(user)
        db.flush()
        record_audit(
            db, actor=None, action="demo.account_created", target_type="user",
            target_id=user.id, school_id=user.school_id, details={"role": role},
        )
        result.append({"role": role, "email": email, "status": "created"})
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Create accounts with public demo credentials.")
    parser.add_argument(
        "--allow-demo-accounts", action="store_true", required=True,
        help="Explicitly allow the four demo accounts on this database.",
    )
    parser.parse_args(argv)
    with get_session_factory()() as db, db.begin():
        accounts = seed_demo_accounts(db)
    for account in accounts:
        print(f"{account['status']}: {account['role']} — {account['email']}")


if __name__ == "__main__":
    main()
