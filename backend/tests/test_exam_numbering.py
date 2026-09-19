"""Display ordinals must not depend on other accounts or search pagination."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.exam import Exam
from app.models.user import User
from app.services.exam_service import ExamService


@pytest.fixture
def numbered_exams(tmp_path):
    service = ExamService()
    engine = create_engine(f"sqlite:///{tmp_path / 'numbering.db'}")
    Base.metadata.create_all(engine)
    service.SessionLocal = sessionmaker(bind=engine)
    with service.SessionLocal() as db:
        db.add_all([
            User(id=1, name="Teacher A", email="a@example.test"),
            User(id=2, name="Teacher B", email="b@example.test"),
        ])
        db.commit()
    a, b = [SimpleNamespace(id=i, school_id=None, role="teacher") for i in (1, 2)]

    def create(actor, grade=8, publication_status="verified"):
        return service._create_exam(
            actor=actor,
            request=SimpleNamespace(
                school="THCS", grade=grade, subject="Khoa học tự nhiên",
                exam_type="Giữa học kì I", duration_minutes=45,
                school_year="2026-2027", total_score=10,
            ),
            matrix=[], summary={}, specification=[], questions=[],
            answer_key=[], rubric=[], validation={},
            publication_status=publication_status,
        )

    rows = [create(a), create(b), create(a, 9), create(a, publication_status="draft"), create(b), create(None)]
    yield service, a, b, rows, engine
    engine.dispose()


@pytest.mark.asyncio
async def test_account_numbers_agree_across_creation_list_search_and_detail(numbered_exams):
    service, a, b, rows, _ = numbered_exams
    assert [row.exam_number for row in rows] == [1, 1, 2, 3, 2, None]
    for actor, expected in [(a, [(rows[3].id, 3), (rows[2].id, 2), (rows[0].id, 1)]),
                            (b, [(rows[4].id, 2), (rows[1].id, 1)])]:
        search = await service.search_exams(actor=actor)
        listed = await service.list_exams(actor=actor)
        assert [(x.id, x.exam_number) for x in search.items] == expected
        assert [(x.id, x.exam_number) for x in listed] == expected
        for exam_id, number in expected:
            detail = await service.get_exam(exam_id, actor=actor)
            assert detail.exam_number == number
            assert detail.model_dump()["exam_number"] == number


@pytest.mark.asyncio
async def test_filters_and_pagination_preserve_account_numbers(numbered_exams):
    service, a, _, rows, _ = numbered_exams
    filtered = await service.search_exams(actor=a, grade=9, page_size=1)
    assert filtered.total == 1
    assert (filtered.items[0].id, filtered.items[0].exam_number) == (rows[2].id, 2)
    for page, expected_number in [(1, 3), (2, 2), (3, 1)]:
        result = await service.search_exams(actor=a, page=page, page_size=1)
        assert result.total == 3
        assert result.items[0].exam_number == expected_number
    listed = await service.list_exams(actor=a, offset=1, limit=1)
    assert listed[0].exam_number == 2
    # Admin/global views retain each creator's sequence.
    admin = SimpleNamespace(id=99, role="super_admin", school_id=None)
    result = await service.search_exams(actor=admin, owner_user_id=a.id, grade=9)
    assert result.items[0].exam_number == 2


@pytest.mark.asyncio
async def test_duplicate_gets_next_owner_number_and_keeps_original_id(numbered_exams):
    service, a, b, rows, _ = numbered_exams
    duplicate = await service.duplicate_exam(rows[0].id, actor=a)
    assert duplicate.id not in {row.id for row in rows}
    assert duplicate.exam_number == 4
    assert (await service.get_exam(rows[0].id, actor=a)).exam_number == 1
    assert (await service.search_exams(actor=b)).items[0].exam_number == 2
    assert (await service.get_exam(duplicate.id, actor=a)).exam_number == 4


@pytest.mark.asyncio
async def test_deletion_compacts_display_numbers_without_changing_ids(numbered_exams):
    service, a, b, rows, _ = numbered_exams
    await service.delete_exam(rows[2].id, actor=a)
    result = await service.search_exams(actor=a)
    assert [(x.id, x.exam_number) for x in result.items] == [(rows[3].id, 2), (rows[0].id, 1)]
    assert (await service.get_exam(rows[3].id, actor=a)).exam_number == 2
    assert (await service.search_exams(actor=b)).items[0].exam_number == 2


@pytest.mark.asyncio
async def test_legacy_ownerless_exams_have_no_number_and_access_is_unchanged(numbered_exams):
    service, a, b, rows, _ = numbered_exams
    assert (await service.get_exam(rows[-1].id)).exam_number is None
    for inaccessible in (rows[-1].id, rows[1].id):
        with pytest.raises(HTTPException) as error:
            await service.get_exam(inaccessible, actor=a)
        assert error.value.status_code == 404
    assert (await service.search_exams(actor=a, owner_user_id=b.id)).total == 0


def test_existing_rows_need_no_column_or_per_exam_query(numbered_exams):
    service, _, _, _, engine = numbered_exams
    assert "exam_number" not in {c["name"] for c in inspect(engine).get_columns("exams")}
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        with service.SessionLocal() as db:
            loaded = db.query(Exam).order_by(Exam.id).all()
            assert [row.exam_number for row in loaded] == [1, 1, 2, 3, 2, None]
        assert len(statements) == 1
    finally:
        event.remove(engine, "before_cursor_execute", record)
