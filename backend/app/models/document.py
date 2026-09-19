from sqlalchemy import Column, ForeignKey, Integer, String, Text, JSON, DateTime, func

from app.core.database import Base


class UploadedDocument(Base):
    """Tài liệu giáo viên upload (Phase 2). Trích xuất text/parsed_data không qua AI."""

    __tablename__ = "uploaded_documents"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    sharing_scope = Column(String(16), nullable=False, default="private", server_default="private", index=True)
    sharing_status = Column(String(16), nullable=False, default="none", server_default="none", index=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(String(1000), nullable=False, default="", server_default="")
    version_id = Column(Integer, nullable=False, default=1, server_default="1")
    filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf | docx | xlsx
    size = Column(Integer, nullable=False, default=0)
    extracted_text = Column(Text, nullable=False, default="")
    parsed_data = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="extracted")  # extracted | failed
    grade = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __mapper_args__ = {"version_id_col": version_id}
