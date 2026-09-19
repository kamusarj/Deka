"""Request leases and exact result pointers; legacy records remain explicitly unlinked."""
from alembic import op
import sqlalchemy as sa
revision = '0005_request_lifecycle'
down_revision = '0004_legacy_adoption'
branch_labels = None
depends_on = None


def upgrade():
    for column in [sa.Column('idempotency_key', sa.String(128)),
                   sa.Column('input_fingerprint', sa.String(64)),
                   sa.Column('lease_owner', sa.String(36)),
                   sa.Column('lease_expires_at', sa.DateTime(timezone=True)),
                   sa.Column('result_exam_id', sa.Integer()), sa.Column('result_version', sa.Integer())]:
        op.add_column('ai_usage', column)
    op.create_index('uq_ai_idempotency', 'ai_usage', ['user_id', 'operation', 'idempotency_key'], unique=True)
    op.create_index('ix_ai_usage_lease', 'ai_usage', ['status', 'lease_expires_at'])


def downgrade():
    raise RuntimeError('Request evidence must be preserved; use an additive rollback')
