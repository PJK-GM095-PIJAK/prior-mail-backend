"""User ORM model.

Maps to Supabase ``auth.users`` via a shared UUID primary key — the ``id`` here
must match the Supabase Auth user ID so JWTs can be validated without a
cross-schema join.

See also:
    - CLAUDE.md §9 — encrypt Gmail refresh tokens at rest (Supabase Vault)
    - docs/DATA_MODELS.md (when available)
"""

from __future__ import annotations

import uuid  # noqa: TC003 — required at runtime by SQLAlchemy Mapped[] resolution

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from priormail.models.orm.db import Base, TimestampMixin, new_uuid


class User(TimestampMixin, Base):
    """A PriorMail user linked to a Google account."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Encrypted Gmail OAuth refresh token — stored via Supabase Vault.
    # NULL until the user completes the Google OAuth flow.
    gmail_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Gmail history ID for delta sync (API historyId is a string of digits).
    gmail_history_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
