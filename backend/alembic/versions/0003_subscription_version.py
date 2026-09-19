"""Version account settings to reject stale or duplicate administrative writes."""
from alembic import op
import sqlalchemy as sa

revision = '0003_subscription_version'
down_revision = '0002_sqlite_account_cleanup'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('user_subscriptions', sa.Column('settings_version', sa.Integer(), nullable=False, server_default='1'))

def downgrade():
    op.drop_column('user_subscriptions', 'settings_version')
