"""Prioritization result ORM model.

Stores the output of the AI pipeline per email: priority classification,
phishing detection, and summary. Fields are populated incrementally as each
LangGraph node runs — ``is_phishing`` / ``phishing_score`` and ``summary`` may
be NULL until those nodes have executed.

See also:
    - CLAUDE.md §7 — ML model integration
    - docs/DATA_MODELS.md (when available)
"""

from __future__ import annotations

import uuid  # noqa: TC003 — required at runtime by SQLAlchemy Mapped[] resolution

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from priormail.models.orm.db import Base, TimestampMixin, new_uuid


class PrioritizationResult(TimestampMixin, Base):
    """AI pipeline output for a single email."""

    __tablename__ = "prioritization_results"
    __table_args__ = (Index("ix_prioritization_email_id", "email_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("emails.id", ondelete="CASCADE"), nullable=False
    )

    # Priority classification (always set).
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)

    # Phishing detection (set by phishing node, may be NULL initially).
    is_phishing: Mapped[bool | None] = mapped_column(nullable=True)
    phishing_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Summary (set by summarizer node, may be NULL initially).
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<PrioritizationResult id={self.id} email_id={self.email_id} "
            f"priority={self.priority!r}>"
        )
