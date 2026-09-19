"""Versioned additive migrations alongside legacy table initialization."""
from pathlib import Path
from alembic import command
from alembic.config import Config

def upgrade_ai_schema(engine):
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / 'alembic.ini'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')


def check_schema(engine):
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / 'alembic.ini'))
    expected = set(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:
        actual = set(MigrationContext.configure(connection).get_current_heads())
    if actual != expected:
        raise RuntimeError('Database revision is incompatible; run the migration release job')
    # A revision marker alone must not bless a damaged or partially adopted schema.
    from sqlalchemy import inspect
    from app.core.database import Base
    from app.models import admin_mfa, document_cleanup, account_token, audit_log, ai_account
    from app.models import bank_question, community, document, exam, school, user
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in tables:
            raise RuntimeError(f'Database table missing: {table.name}')
        reflected = {column['name']: column for column in inspector.get_columns(table.name)}
        columns = set(reflected)
        if not set(table.columns.keys()) <= columns:
            raise RuntimeError(f'Database columns incompatible: {table.name}')
        for column in table.columns:
            actual_column = reflected[column.name]
            if column.type._type_affinity != actual_column['type']._type_affinity:
                raise RuntimeError(f'Database type incompatible: {table.name}.{column.name}')
            if not column.nullable and not column.primary_key and actual_column['nullable']:
                raise RuntimeError(f'Database nullability incompatible: {table.name}.{column.name}')
        primary = set(inspector.get_pk_constraint(table.name)['constrained_columns'])
        if primary != {c.name for c in table.primary_key}:
            raise RuntimeError(f'Database primary key incompatible: {table.name}')
        from sqlalchemy import UniqueConstraint, CheckConstraint
        actual_unique = {tuple(row['column_names']) for row in inspector.get_unique_constraints(table.name)}
        actual_unique.update(tuple(row['column_names']) for row in inspector.get_indexes(table.name) if row.get('unique'))
        required_unique = {tuple(c.name for c in constraint.columns) for constraint in table.constraints if isinstance(constraint, UniqueConstraint)}
        required_unique.update(tuple(c.name for c in index.columns) for index in table.indexes if index.unique)
        if not required_unique <= actual_unique:
            raise RuntimeError(f'Database uniqueness incompatible: {table.name}')
        checks = {row['name'] for row in inspector.get_check_constraints(table.name)}
        if not {c.name for c in table.constraints if isinstance(c, CheckConstraint)} <= checks:
            raise RuntimeError(f'Database checks incompatible: {table.name}')


if __name__ == '__main__':
    from app.core.config import settings
    from app.core.database import _create_session_factory
    engine, _ = _create_session_factory(settings.DATABASE_URL)
    try:
        upgrade_ai_schema(engine)
        check_schema(engine)
    finally:
        engine.dispose()
