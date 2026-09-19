"""Encrypted TOTP enrollment and single-use recovery hashes."""
from alembic import op
import sqlalchemy as sa
revision = '0007_admin_mfa'
down_revision = '0006_document_cleanup'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if 'admin_mfa' in inspector.get_table_names():
        if {column['name'] for column in inspector.get_columns('admin_mfa')} != {'encrypted_secret', 'recovery_hashes', 'last_counter', 'enabled', 'user_id'}:
            raise RuntimeError('Existing admin_mfa schema does not match the release')
        return
    op.create_table('admin_mfa',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('encrypted_secret', sa.String(500), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('last_counter', sa.Integer(), nullable=False, server_default='-1'),
        sa.Column('recovery_hashes', sa.JSON(), nullable=False))


def downgrade():
    raise RuntimeError('MFA credentials cannot be removed by release rollback')
