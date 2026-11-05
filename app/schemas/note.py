from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

from app.models.note import TITLE_MAX_LENGTH

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX_LENGTH),
]


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: Title
    body: str | None = None


class NoteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: Title | None = None
    body: str | None = None

    @model_validator(mode="after")
    def _check_fields(self) -> "NoteUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one of title or body is required")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title must not be null")
        return self


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _assume_utc(cls, value: datetime) -> datetime:
        # Timestamps are always written in UTC, but some backends (SQLite) drop tzinfo.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class NotePage(BaseModel):
    items: list[NoteRead]
    total: int
    limit: int
    offset: int
