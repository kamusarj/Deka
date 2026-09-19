from sqlalchemy import create_engine, inspect, text
from app.core.migrations import upgrade_ai_schema

def test_additive_migration_preserves_legacy_rows_and_replays(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path}/legacy.db')
    with engine.begin() as db:
        db.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)'))
        db.execute(text("INSERT INTO users VALUES (1, 'existing@example.test')"))
        db.execute(text('CREATE TABLE exams (id INTEGER PRIMARY KEY, name TEXT)'))
        db.execute(text("INSERT INTO exams VALUES (3, 'existing exam')"))
    upgrade_ai_schema(engine)
    upgrade_ai_schema(engine)
    assert {'ai_usage', 'credit_transactions', 'user_subscriptions'} <= set(inspect(engine).get_table_names())
    with engine.connect() as db:
        assert db.execute(text('SELECT email FROM users')).scalar_one() == 'existing@example.test'
        assert db.execute(text('SELECT name FROM exams')).scalar_one() == 'existing exam'
        assert db.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0007_admin_mfa'
        # Legacy SQLite connections leave foreign_keys disabled. Deleting a
        # user must still remove accounting before SQLite can reuse that ID.
        db.execute(text("INSERT INTO user_subscriptions (user_id,plan,status,credit_allowance,credit_balance,current_period_start,current_period_end) VALUES (1,'FREE','active',50,50,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        db.execute(text('DELETE FROM users WHERE id=1'))
        assert db.execute(text('SELECT count(*) FROM user_subscriptions')).scalar_one() == 0


def test_cost_known_cached_unknown_and_invalid():
    from decimal import Decimal
    from app.services.ai.gateway import TokenUsage
    from app.services.ai.pricing import AICostCalculator
    calc = AICostCalculator({'openai:test': {'input': '2', 'output': '8', 'cached_input': '1'}})
    assert calc.calculate('openai', 'test', TokenUsage(100, 20, 40)) == Decimal('0.00032')
    assert calc.calculate('openai', 'unknown', TokenUsage(100, 20, 40)) is None
    assert calc.calculate('openai', 'test', TokenUsage()) is None
    assert AICostCalculator({'p:m': {'input': 'NaN', 'output': '1'}}).calculate('p', 'm', TokenUsage(1, 2)) is None


def test_subscription_version_upgrade_preserves_existing_account(tmp_path):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    engine = create_engine(f'sqlite:///{tmp_path}/accounts-v2.db')
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    with engine.begin() as db:
        db.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        db.execute(text('INSERT INTO users VALUES (1)'))
        config.attributes['connection'] = db
        command.upgrade(config, '0002_sqlite_account_cleanup')
        db.execute(text("INSERT INTO user_subscriptions (user_id,plan,status,credit_allowance,credit_balance,current_period_start,current_period_end) VALUES (1,'PRO','active',1900,123,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    upgrade_ai_schema(engine)
    with engine.connect() as db:
        assert db.execute(text('SELECT plan,credit_allowance,credit_balance,settings_version FROM user_subscriptions')).one() == ('PRO',1900,123,1)
    engine.dispose()
