"""Additive account and accounting tables. Credits are always integers."""
from uuid import uuid4
from sqlalchemy import (CheckConstraint, Column, DateTime, ForeignKey, Index,
                        Integer, Numeric, String, UniqueConstraint, func)
from app.core.database import Base

class UserSubscription(Base):
    __tablename__ = 'user_subscriptions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    plan = Column(String(40), nullable=False)
    status = Column(String(24), nullable=False)
    settings_version = Column(Integer, nullable=False, default=1, server_default='1')
    credit_allowance = Column(Integer, nullable=False)
    credit_balance = Column(Integer, nullable=False)
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (CheckConstraint('credit_balance >= 0', name='ck_subscription_balance'),
                     CheckConstraint('credit_allowance >= 0', name='ck_subscription_allowance'))

class CreditTransaction(Base):
    __tablename__ = 'credit_transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    type = Column(String(32), nullable=False)
    reference_id = Column(String(80), nullable=False)
    description = Column(String(255), nullable=False, default='')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'type', 'reference_id', name='uq_credit_reference'),)

class AIUsage(Base):
    __tablename__ = 'ai_usage'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    request_id = Column(String(36), nullable=False)
    record_kind = Column(String(16), nullable=False)  # request summary or provider attempt
    provider_request_id = Column(String(255), nullable=True)
    provider = Column(String(32), nullable=True)
    model = Column(String(200), nullable=True)
    operation = Column(String(40), nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    cached_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Numeric(20, 10), nullable=True)
    credits_charged = Column(Integer, nullable=False, default=0)
    reserved_credits = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=False, default=0)
    status = Column(String(24), nullable=False)
    error_code = Column(String(40), nullable=True)
    idempotency_key = Column(String(128), nullable=True)
    input_fingerprint = Column(String(64), nullable=True)
    lease_owner = Column(String(36), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    result_exam_id = Column(Integer, nullable=True)
    result_version = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (Index('ix_ai_usage_user_created', 'user_id', 'created_at'),
                     UniqueConstraint('user_id', 'operation', 'idempotency_key', name='uq_ai_idempotency'),
                     Index('ix_ai_usage_lease', 'status', 'lease_expires_at'),
                     Index('ix_ai_usage_request', 'request_id'),
                     CheckConstraint('credits_charged >= 0 AND reserved_credits >= 0', name='ck_usage_credits'))
