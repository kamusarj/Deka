from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, JSON
from app.core.database import Base


class AdminMFA(Base):
    __tablename__ = 'admin_mfa'
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    encrypted_secret = Column(String(500), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False, server_default='0')
    last_counter = Column(Integer, nullable=False, default=-1, server_default='-1')
    recovery_hashes = Column(JSON, nullable=False, default=list)
