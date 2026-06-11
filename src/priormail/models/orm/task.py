"""Extracted task ORM model.

Tasks are extracted from emails by the ``extract_tasks`` LangGraph node.
Users can mark them complete or edit them through the API
(``PATCH /api/v1/tasks/{id}`` — API_CONTRACT.md §6).

See also:
    - docs/DATA_MODELS.md (when available)
"""

from __future__ import annotations

import uuid  # noqa: TC003 — required at runtime by SQLAlchemy Mapped[] resolution
from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from priormail.models.orm.db import Base, TimestampMixin, new_uuid


class ExtractedTask(TimestampMixin, Base):
    """An actionable task extracted from an email by the AI pipeline."""

    __tablename__ = "extracted_tasks"
    __table_args__ = (
        Index("ix_tasks_user_completed", "user_id", "is_completed"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("emails.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<ExtractedTask id={self.id} title={self.title!r} done={self.is_completed}>"
