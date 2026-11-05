from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Note


class NoteNotFound(Exception):
    def __init__(self, note_id: int):
        super().__init__(f"Note {note_id} not found")
        self.note_id = note_id


def create_note(session: Session, *, title: str, body: str | None = None) -> Note:
    note = Note(title=title, body=body)
    session.add(note)
    session.commit()
    return note


def list_notes(session: Session) -> list[Note]:
    stmt = select(Note).order_by(Note.created_at.desc(), Note.id.desc())
    return list(session.scalars(stmt))


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
