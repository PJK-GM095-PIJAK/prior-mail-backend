"""Email ORM model.

Stores synced Gmail messages. Raw bodies are deleted after 30 days — only the
SHA-256 hash and AI-derived fields survive (CLAUDE.md §9).

See also:
    - docs/DATA_MODELS.md (when available)
    - CLAUDE.md §9 — "Delete raw email bodies after 30 days"
"""

from __future__ import annotations

import uuid  # noqa: TC003 — required at runtime by SQLAlchemy Mapped[] resolution
from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from priormail.models.orm.db import Base, TimestampMixin, new_uuid


class Email(TimestampMixin, Base):
    """A Gmail message synced for a specific user."""

    __tablename__ = "emails"
    __table_args__ = (
        # Prevent duplicate sync of the same Gmail message.
        Index("uq_emails_user_gmail", "user_id", "gmail_id", unique=True),
        # Primary query pattern: newest emails for a user.
        Index("ix_emails_user_received", "user_id", "received_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Gmail identifiers
    gmail_id: Mapped[str] = mapped_column(String(64), nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Email metadata
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sender: Mapped[str] = mapped_column(String(320), nullable=False)
    recipients: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    received_at: Mapped[datetime] = mapped_column(nullable=False)

    # Body — raw_body is deleted after 30 days; body_hash persists.
    body_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Gmail state
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    labels: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<Email id={self.id} gmail_id={self.gmail_id!r} subject={self.subject!r}>"
