from pathlib import Path
from threading import Lock

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

Base = declarative_base()

_engine = None
_SessionLocal = None
_database_url = settings.DATABASE_URL
_init_lock = Lock()


def _sqlite_fallback_url() -> str:
    data_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'smart_exam.db'}"


def _create_session_factory(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    if database_url.startswith("postgresql"):
        connect_args = {"connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS}
    engine = create_engine(database_url, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


def init_db():
    global _engine, _SessionLocal, _database_url

    is_postgres = settings.DATABASE_URL.startswith("postgresql")
    is_local_mode = settings.ENV.strip().lower() in {"development", "dev", "test", "testing"}
    if is_postgres and is_local_mode and not settings.USE_POSTGRES:
        selected_url = _sqlite_fallback_url()
    else:
        selected_url = settings.DATABASE_URL

    with _init_lock:
        if _engine is not None and _SessionLocal is not None and _database_url == selected_url:
            return _engine

        try:
            next_engine, next_session_factory = _create_session_factory(selected_url)
            if is_postgres and selected_url == settings.DATABASE_URL:
                # Let the database driver perform a real authenticated connection
                # check. A 200ms raw TCP probe can report false negatives and says
                # nothing about credentials/database availability.
                with next_engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
        except Exception as exc:
            if is_postgres and selected_url == settings.DATABASE_URL:
                raise RuntimeError(
                    "PostgreSQL không khả dụng; từ chối fallback sang SQLite để tránh phục vụ dữ liệu trống"
                ) from exc
            raise

        from app.models.account_token import AccountToken  # noqa: F401
        from app.models.audit_log import AuditLog  # noqa: F401
        from app.models.bank_question import BankQuestion  # noqa: F401
        from app.models.community import CommunityComment, CommunityTopic  # noqa: F401
        from app.models.document import UploadedDocument  # noqa: F401
        from app.models.exam import Exam  # noqa: F401
        from app.models.school import School  # noqa: F401
        from app.models.user import User  # noqa: F401

        from app.core.migrations import upgrade_ai_schema, check_schema
        if settings.deployed:
            check_schema(next_engine)
        else:
            upgrade_ai_schema(next_engine)
        _engine = next_engine
        _SessionLocal = next_session_factory
        _database_url = selected_url
        return _engine


def _migrate_compatibility_columns(engine):
    """Add narrow compatibility columns to pre-existing MVP databases.

    The project previously used ``create_all`` without a migration runner. This
    deliberately narrow, idempotent migration keeps old SQLite/PostgreSQL data
    readable while new rows can be tenant-scoped. Legacy rows remain unassigned
    and are intentionally not exposed through authenticated tenant APIs.
    """
    inspector = inspect(engine)
    is_postgresql = engine.dialect.name == "postgresql"
    boolean_true = (
        "BOOLEAN NOT NULL DEFAULT TRUE" if is_postgresql else "BOOLEAN NOT NULL DEFAULT 1"
    )
    boolean_false = (
        "BOOLEAN NOT NULL DEFAULT FALSE" if is_postgresql else "BOOLEAN NOT NULL DEFAULT 0"
    )
    timestamp_type = "TIMESTAMP WITH TIME ZONE" if is_postgresql else "TIMESTAMP"
    required_by_table = {
        "exams": {
            "owner_user_id": "INTEGER",
            "school_id": "INTEGER",
            "publication_status": "VARCHAR(32) NOT NULL DEFAULT 'verified'",
            "version_id": "INTEGER NOT NULL DEFAULT 1",
        },
        "uploaded_documents": {
            "owner_user_id": "INTEGER", "school_id": "INTEGER",
            "sharing_scope": "VARCHAR(16) NOT NULL DEFAULT 'private'",
            "sharing_status": "VARCHAR(16) NOT NULL DEFAULT 'none'",
            "reviewed_by_user_id": "INTEGER",
            "reviewed_at": timestamp_type,
            "review_note": "VARCHAR(1000) NOT NULL DEFAULT ''",
            "version_id": "INTEGER NOT NULL DEFAULT 1",
        },
        "bank_questions": {"owner_user_id": "INTEGER", "school_id": "INTEGER", "rich_content": "JSON", "content_metadata": "JSON"},
        "users": {
            "token_version": "INTEGER NOT NULL DEFAULT 0",
            "email_verified": boolean_true,
            "must_change_password": boolean_false,
            "deleted_at": timestamp_type,
        },
    }
    for table_name, required in required_by_table.items():
        if table_name not in inspector.get_table_names():
            continue
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, definition in required.items():
            if column_name not in existing:
                with engine.begin() as connection:
                    connection.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
                    )

    if "exams" in inspector.get_table_names():
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_exams_publication_status "
                    "ON exams (publication_status)"
                )
            )

    if "uploaded_documents" in inspector.get_table_names():
        with engine.begin() as connection:
            for column in ("sharing_scope", "sharing_status"):
                connection.execute(text(
                    f"CREATE INDEX IF NOT EXISTS ix_uploaded_documents_{column} "
                    f"ON uploaded_documents ({column})"
                ))


def get_session_factory():
    if _SessionLocal is None:
        init_db()
    return _SessionLocal


def get_database_url() -> str:
    return _database_url


def get_db():
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
