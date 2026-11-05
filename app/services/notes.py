from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Note

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100
SEARCH_MAX_LENGTH = 100

_LIKE_ESCAPE = "\\"


class NoteNotFound(Exception):
    def __init__(self, note_id: int):
        super().__init__(f"Note {note_id} not found")
        self.note_id = note_id


def create_note(session: Session, *, title: str, body: str | None = None) -> Note:
    note = Note(title=title, body=body)
    session.add(note)
    session.commit()
    return note


def _escape_like(value: str) -> str:
    return (
        value.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", _LIKE_ESCAPE + "%")
        .replace("_", _LIKE_ESCAPE + "_")
    )


def list_notes(
    session: Session,
    *,
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = 0,
    q: str | None = None,
) -> tuple[list[Note], int]:
    """Return one page of notes (newest first) and the total count matching ``q``."""
    conditions = []
    term = q.strip() if q else ""
    if term:
        pattern = f"%{_escape_like(term)}%"
        conditions.append(
            or_(
                Note.title.ilike(pattern, escape=_LIKE_ESCAPE),
                Note.body.ilike(pattern, escape=_LIKE_ESCAPE),
            )
        )

    total = session.scalar(select(func.count()).select_from(Note).where(*conditions))
    stmt = (
        select(Note)
        .where(*conditions)
        .order_by(Note.created_at.desc(), Note.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(stmt)), total or 0


def get_note(session: Session, note_id: int) -> Note:
    note = session.get(Note, note_id)
    if note is None:
        raise NoteNotFound(note_id)
    return note


def update_note(session: Session, note_id: int, changes: dict[str, Any]) -> Note:
    note = get_note(session, note_id)
    for field, value in changes.items():
        setattr(note, field, value)
    session.commit()
    return note


def delete_note(session: Session, note_id: int) -> None:
    note = get_note(session, note_id)
    session.delete(note)
    session.commit()
