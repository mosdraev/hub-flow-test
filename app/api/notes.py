from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas import NoteCreate, NoteRead, NoteUpdate
from app.services import notes as service

router = APIRouter(prefix="/notes", tags=["notes"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(payload: NoteCreate, session: SessionDep):
    return service.create_note(session, title=payload.title, body=payload.body)


@router.get("", response_model=list[NoteRead])
def list_notes(session: SessionDep):
    return service.list_notes(session)


@router.get("/{note_id}", response_model=NoteRead)
def get_note(note_id: int, session: SessionDep):
    return service.get_note(session, note_id)


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(note_id: int, payload: NoteUpdate, session: SessionDep):
    return service.update_note(session, note_id, payload.model_dump(exclude_unset=True))


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, session: SessionDep) -> Response:
    service.delete_note(session, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
