from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, case, func, select
from sqlalchemy.orm import column_property

from app.core.database import Base


class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    # Nullable while existing installations are migrated. New API-created rows
    # always set these fields before persistence.
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    school = Column(String, nullable=False)
    grade = Column(Integer, nullable=False)
    subject = Column(String, nullable=False, default="Khoa học tự nhiên")
    exam_type = Column(String, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    school_year = Column(String, nullable=False)
    total_score = Column(Float, default=10.0)

    matrix = Column(JSON, nullable=False)
    summary = Column(JSON, nullable=False)
    specification = Column(JSON, nullable=False)
    questions = Column(JSON, nullable=False)
    answer_key = Column(JSON, nullable=False)
    rubric = Column(JSON, nullable=False)
    validation = Column(JSON, nullable=False)
    resource_package = Column(JSON, nullable=True)
    review_status = Column(JSON, nullable=False, default=dict)
    publication_status = Column(
        String,
        nullable=False,
        default="verified",
        server_default="verified",
        index=True,
    )
    version_id = Column(Integer, nullable=False, default=1, server_default="1")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __mapper_args__ = {"version_id_col": version_id}


# Display order among the owner's remaining exams, not a persistent identifier.
# Correlation keeps numbers independent of outer filters, pagination and viewer.
# Load in the exam SELECT so serializing a page does not issue N extra queries.
_owner_exams = Exam.__table__.alias("owner_exams")
Exam.exam_number = column_property(
    case(
        (
            Exam.owner_user_id.is_not(None),
            select(func.count(_owner_exams.c.id))
            .where(
                _owner_exams.c.owner_user_id == Exam.owner_user_id,
                _owner_exams.c.id <= Exam.id,
            )
            .correlate_except(_owner_exams)
            .scalar_subquery(),
        ),
        else_=None,
    )
)
