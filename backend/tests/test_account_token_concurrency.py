"""One-use account links are claimed inside the account transaction."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.account_token import AccountToken
from app.models.user import User
from app.services.account_token_service import (
    RESET_PASSWORD, VERIFY_EMAIL, consume_account_token, issue_account_token,
)


@pytest.fixture
def token_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tokens.db'}", connect_args={"check_same_thread": False, "timeout": 10})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions() as db:
        user = User(email="tokens@example.test", name="Token owner", role="teacher", is_active=True)
        db.add(user); db.commit(); user_id = user.id
    yield engine, sessions, user_id
    engine.dispose()


@pytest.mark.parametrize("purpose", [RESET_PASSWORD, VERIFY_EMAIL])
def test_concurrent_consumers_cannot_both_commit_one_link(token_store, purpose):
    engine, sessions, user_id = token_store
    with sessions() as db:
        raw = issue_account_token(db, user_id, purpose); db.commit()
    start = Barrier(2)
    selected = Barrier(2)

    # Force two vulnerable read-then-write consumers to finish their eligibility
    # SELECT before either commits. An atomic UPDATE claim needs no such SELECT.
    def synchronize_eligibility_reads(_conn, _cursor, statement, _params, _context, _many):
        sql = statement.lower()
        if sql.lstrip().startswith("select") and "account_tokens.used_at is null" in sql:
            selected.wait(timeout=5)

    event.listen(engine, "after_cursor_execute", synchronize_eligibility_reads)

    def attempt():
        with sessions() as db:
            start.wait(timeout=5)
            try:
                consume_account_token(db, raw, purpose)
                db.commit()
                return "accepted"
            except HTTPException as error:
                db.rollback()
                return error.status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
    finally:
        event.remove(engine, "after_cursor_execute", synchronize_eligibility_reads)
    assert results.count("accepted") == 1, results
    assert results.count(400) == 1, results


def test_claim_cannot_repeat_before_commit_and_is_restored_on_rollback(token_store):
    _engine, sessions, user_id = token_store
    with sessions() as db:
        raw = issue_account_token(db, user_id, RESET_PASSWORD); db.commit()
    with sessions() as db:
        assert consume_account_token(db, raw, RESET_PASSWORD).user_id == user_id
        with pytest.raises(HTTPException) as error:
            consume_account_token(db, raw, RESET_PASSWORD)
        assert error.value.status_code == 400
        db.rollback()
    with sessions() as db:
        consume_account_token(db, raw, RESET_PASSWORD)
        db.commit()
    with sessions() as db:
        with pytest.raises(HTTPException):
            consume_account_token(db, raw, RESET_PASSWORD)


def test_wrong_purpose_and_expiry_do_not_consume_a_valid_link(token_store):
    _engine, sessions, user_id = token_store
    with sessions() as db:
        raw = issue_account_token(db, user_id, RESET_PASSWORD); db.commit()
        with pytest.raises(HTTPException):
            consume_account_token(db, raw, VERIFY_EMAIL)
        db.rollback()
        row = db.query(AccountToken).one()
        assert row.used_at is None
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        with pytest.raises(HTTPException):
            consume_account_token(db, raw, RESET_PASSWORD)
        db.rollback()
        assert db.query(AccountToken).one().used_at is None
