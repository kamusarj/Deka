from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.bank_question import BankQuestion
from app.models.document import UploadedDocument
from app.models.exam import Exam
from app.models.school import School
from app.models.user import User
from app.schemas.dashboard import DashboardSummary
from app.services.auth_service import get_current_user
from app.services.authorization import scope_query
from app.services.document_access import document_access_filter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    exam_query = scope_query(db.query(Exam), Exam, user)
    document_query = db.query(UploadedDocument).filter(document_access_filter(user))
    bank_query = scope_query(db.query(BankQuestion), BankQuestion, user)
    exams = exam_query.order_by(Exam.created_at.desc(), Exam.id.desc()).all()

    payload = {
        "role": user.role,
        "scope_label": {
            "super_admin": "Toàn hệ thống",
            "school_admin": "Trong trường",
            "teacher": "Của tôi",
            "viewer": "Được phép xem",
        }.get(user.role, "Của tôi"),
        "exams": len(exams),
        "questions": sum(len(exam.questions or []) for exam in exams),
        "documents": document_query.count(),
        "bank_questions": bank_query.count(),
        "recent_exam_ids": [exam.id for exam in exams[:5]],
    }
    if user.role == "super_admin":
        payload["schools"] = db.query(School).count()
        payload["users"] = db.query(User).filter(
            User.deleted_at.is_(None), User.is_active.is_(True)
        ).count()
    elif user.role == "school_admin":
        payload["teachers"] = db.query(User).filter(
            User.school_id == user.school_id,
            User.role == "teacher",
            User.deleted_at.is_(None),
        ).count()
    return DashboardSummary(**payload)
