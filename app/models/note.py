from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db import Base

TITLE_MAX_LENGTH = 255


def utcnow() -> datetime:
    return datetime.now(UTC)


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    @validates("title")
    def _validate_title(self, _key: str, value: str | None) -> str:
        if value is None:
            raise ValueError("title is required")
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        if len(value) > TITLE_MAX_LENGTH:
            raise ValueError(f"title must be at most {TITLE_MAX_LENGTH} characters")
        return value

    def __repr__(self) -> str:
        return f"<Note id={self.id} title={self.title!r}>"
