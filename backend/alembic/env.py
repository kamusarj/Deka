"""Use the same database selection as the application; no secret URL in ini."""
from alembic import context
from sqlalchemy import create_engine
from app.core.config import settings
from app.core.database import _sqlite_fallback_url

config = context.config

def migrate(connection):
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()

connection = config.attributes.get('connection')
if connection is not None:
    migrate(connection)
else:
    url = settings.DATABASE_URL
    if url.startswith('postgresql') and settings.ENV.lower() in {'development', 'dev', 'test', 'testing'} and not settings.USE_POSTGRES:
        url = _sqlite_fallback_url()
    if context.is_offline_mode():
        context.configure(url=url, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_engine(url)
        with engine.connect() as connection:
            migrate(connection)
        engine.dispose()
