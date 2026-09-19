"""Add development AI accounts without altering existing application tables."""
from alembic import op
import sqlalchemy as sa

revision = '0001_ai_accounts'
down_revision = '0000_legacy_schema'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('user_subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('plan', sa.String(40), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('credit_allowance', sa.Integer(), nullable=False),
        sa.Column('credit_balance', sa.Integer(), nullable=False),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('credit_balance >= 0', name='ck_subscription_balance'),
        sa.CheckConstraint('credit_allowance >= 0', name='ck_subscription_allowance'))
    op.create_table('credit_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(32), nullable=False),
        sa.Column('reference_id', sa.String(80), nullable=False),
        sa.Column('description', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('user_id', 'type', 'reference_id', name='uq_credit_reference'))
    op.create_index('ix_credit_transactions_user_id', 'credit_transactions', ['user_id'])
    op.create_table('ai_usage',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('record_kind', sa.String(16), nullable=False),
        sa.Column('provider_request_id', sa.String(255)),
        sa.Column('provider', sa.String(32)), sa.Column('model', sa.String(200)),
        sa.Column('operation', sa.String(40), nullable=False),
        sa.Column('input_tokens', sa.Integer()), sa.Column('output_tokens', sa.Integer()),
        sa.Column('cached_tokens', sa.Integer()), sa.Column('estimated_cost_usd', sa.Numeric(20, 10)),
        sa.Column('credits_charged', sa.Integer(), nullable=False),
        sa.Column('reserved_credits', sa.Integer(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(24), nullable=False), sa.Column('error_code', sa.String(40)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('credits_charged >= 0 AND reserved_credits >= 0', name='ck_usage_credits'))
    op.create_index('ix_ai_usage_user_created', 'ai_usage', ['user_id', 'created_at'])
    op.create_index('ix_ai_usage_request', 'ai_usage', ['request_id'])

def downgrade():
    op.drop_table('ai_usage')
    op.drop_table('credit_transactions')
    op.drop_table('user_subscriptions')
