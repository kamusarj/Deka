"""Deletion tombstones, retained for retry and restore reconciliation."""
from alembic import op
import sqlalchemy as sa
revision = '0006_document_cleanup'
down_revision = '0005_request_lifecycle'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if 'document_cleanup' in inspector.get_table_names():
        if {column['name'] for column in inspector.get_columns('document_cleanup')} != {'attempts', 'document_id', 'error_type', 'stored_filename', 'created_at', 'id', 'status', 'owner_user_id'}:
            raise RuntimeError('Existing document_cleanup schema does not match the release')
        return
    op.create_table('document_cleanup',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('document_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('owner_user_id', sa.Integer()),
        sa.Column('stored_filename', sa.String(500), nullable=False),
        sa.Column('status', sa.String(24), nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_type', sa.String(80)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    raise RuntimeError('Deletion evidence must survive rollback and restore')
