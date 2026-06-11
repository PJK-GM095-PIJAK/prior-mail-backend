"""Audit log ORM model.

Every email content access must be logged here (CLAUDE.md §9). This is
append-only — rows are never updated or deleted.

See also:
    - CLAUDE.md §9 — "Log every email content access in audit_log table"
    - docs/SECURITY.md (when available)
"""

from __future__ import annotations

import uuid  # noqa: TC003 — required at runtime by SQLAlchemy Mapped[] resolution
from datetime import datetime  # noqa: TC003

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from priormail.models.orm.db import Base, new_uuid


class AuditLog(Base):
    """Append-only log of security-relevant actions.

    Does **not** use ``TimestampMixin`` because audit rows are immutable — there
    is no ``updated_at``.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Action performed, e.g. "email.body_read", "email.delete", "task.update".
    action: Mapped[str] = mapped_column(String(64), nullable=False)

    # Type of resource involved, e.g. "email", "task", "user".
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # ID of the affected resource (nullable for actions without a specific target).
    resource_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    # Additional structured context (must never contain email bodies).
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} action={self.action!r} "
            f"resource={self.resource_type}:{self.resource_id}>"
        )
