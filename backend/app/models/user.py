from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for OAuth users
    name = Column(String(255), nullable=False, default="")
    role = Column(String(50), nullable=False, default="teacher")  # super_admin, school_admin, teacher, viewer
    is_active = Column(Boolean, nullable=False, default=True)
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    email_verified = Column(Boolean, nullable=False, default=True, server_default="1")
    must_change_password = Column(Boolean, nullable=False, default=False, server_default="0")
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # School relationship
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)

    # OAuth fields
    oauth_provider = Column(String(50), nullable=True)  # google, facebook
    oauth_id = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
