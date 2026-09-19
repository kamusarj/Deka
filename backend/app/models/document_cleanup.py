"""Durable deletion evidence contains identifiers only, never extracted content."""
from sqlalchemy import Column, DateTime, Integer, String, func
from app.core.database import Base


class DocumentCleanup(Base):
    __tablename__ = 'document_cleanup'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, nullable=False, unique=True)
    owner_user_id = Column(Integer, nullable=True)
    stored_filename = Column(String(500), nullable=False)
    status = Column(String(24), nullable=False, default='pending', server_default='pending')
    attempts = Column(Integer, nullable=False, default=0, server_default='0')
    error_type = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
