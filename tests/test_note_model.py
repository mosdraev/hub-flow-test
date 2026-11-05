import time

import pytest
from sqlalchemy import select

from app.models import Note
from app.models.note import TITLE_MAX_LENGTH


def _save(session, **kwargs) -> Note:
    note = Note(**kwargs)
    session.add(note)
    session.commit()
    return note


# Happy path


def test_create_note_with_title_and_body(session):
    note = _save(session, title="Groceries", body="eggs, rice")

    assert note.id is not None
    assert note.created_at is not None
    assert note.updated_at is not None

    loaded = session.scalars(select(Note).where(Note.id == note.id)).one()
    assert loaded.title == "Groceries"
    assert loaded.body == "eggs, rice"


def test_create_note_title_only_body_is_none(session):
    note = _save(session, title="Just a title")
    assert note.body is None


def test_update_advances_updated_at_not_created_at(session):
    note = _save(session, title="Before")
    # Reload so both sides of the comparison come from the DB (SQLite drops tzinfo).
    session.refresh(note)
    created, updated = note.created_at, note.updated_at

    time.sleep(0.01)
    note.title = "After"
    session.commit()
    session.refresh(note)

    assert note.title == "After"
    assert note.created_at == created
    assert note.updated_at > updated


# Failure path


def test_title_none_rejected():
    with pytest.raises(ValueError, match="required"):
        Note(title=None)


@pytest.mark.parametrize("title", ["", "   ", "\t\n"])
def test_blank_title_rejected(title):
    with pytest.raises(ValueError, match="blank"):
        Note(title=title)


def test_title_over_max_length_rejected():
    with pytest.raises(ValueError, match=str(TITLE_MAX_LENGTH)):
        Note(title="a" * (TITLE_MAX_LENGTH + 1))


def test_missing_title_fails_at_db_level(session):
    session.add(Note(body="no title"))
    with pytest.raises(Exception):  # noqa: B017  (IntegrityError from the NOT NULL constraint)
        session.commit()
    session.rollback()


# Edge cases


def test_title_at_max_length_accepted(session):
    note = _save(session, title="a" * TITLE_MAX_LENGTH)
    assert len(note.title) == TITLE_MAX_LENGTH


def test_title_is_trimmed(session):
    note = _save(session, title="  padded  ")
    assert note.title == "padded"


def test_unicode_round_trips(session):
    note = _save(session, title="Bayad sa InstaPay ✅", body="Salamat po 🙏 ñ é 漢字")
    session.expire_all()
    loaded = session.get(Note, note.id)
    assert loaded.title == "Bayad sa InstaPay ✅"
    assert loaded.body == "Salamat po 🙏 ñ é 漢字"


def test_large_body_stored_intact(session):
    body = "x" * 1_000_000
    note = _save(session, title="Big", body=body)
    session.expire_all()
    assert session.get(Note, note.id).body == body
