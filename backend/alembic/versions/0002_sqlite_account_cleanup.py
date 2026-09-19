"""Preserve AI-account cascade semantics in legacy SQLite connections.

The existing SQLite factory does not enable foreign_keys. Do not change legacy
relationships globally: scope equivalent cascade behavior to the new AI tables.
"""
from alembic import op

revision = '0002_sqlite_account_cleanup'
down_revision = '0001_ai_accounts'
branch_labels = None
depends_on = None

def upgrade():
    if op.get_bind().dialect.name == 'sqlite':
        op.execute('''CREATE TRIGGER ai_accounts_user_delete AFTER DELETE ON users
        BEGIN
          DELETE FROM ai_usage WHERE user_id = OLD.id;
          DELETE FROM credit_transactions WHERE user_id = OLD.id;
          DELETE FROM user_subscriptions WHERE user_id = OLD.id;
        END''')

def downgrade():
    if op.get_bind().dialect.name == 'sqlite':
        op.execute('DROP TRIGGER ai_accounts_user_delete')
