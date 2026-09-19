from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=False, index=True)
    target_id = Column(Integer, nullable=True, index=True)
    # Keep the identifier even after a conservatively allowed school deletion.
    school_id = Column(Integer, nullable=True, index=True)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
