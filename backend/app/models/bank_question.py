from sqlalchemy import Column, ForeignKey, Integer, Float, String, Text, JSON, DateTime, func

from app.core.database import Base


class BankQuestion(Base):
    """Câu hỏi trong ngân hàng đề (Phase 2). Không gọi AI."""

    __tablename__ = "bank_questions"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    type = Column(String, nullable=False)  # multiple_choice | true_false | short_answer | essay
    difficulty = Column(String, nullable=False, default="thong_hieu")
    topic = Column(String, nullable=True)
    grade = Column(Integer, nullable=True)
    subject = Column(String, nullable=False, default="Khoa học tự nhiên")
    tags = Column(JSON, nullable=False, default=list)

    options = Column(JSON, nullable=True)        # multiple_choice
    statements = Column(JSON, nullable=True)     # true_false
    sub_questions = Column(JSON, nullable=True)  # essay
    answer = Column(JSON, nullable=True)         # đáp án / rubric kèm theo
    source = Column(JSON, nullable=True)
    rich_content = Column(JSON, nullable=True)
    content_metadata = Column(JSON, nullable=True)

    usage_count = Column(Integer, nullable=False, default=0)
    rating = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
