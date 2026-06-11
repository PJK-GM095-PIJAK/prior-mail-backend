"""SQLAlchemy declarative base, async engine, and session factory.

All ORM models inherit from :class:`Base`. The engine is created once at app
startup via :func:`create_db_engine` and stored on ``app.state``; route handlers
obtain sessions through the ``get_db`` dependency (``core/deps.py``).

References:
    - alembic/env.py — imports ``Base.metadata`` for autogenerate
    - core/deps.py   — ``get_db`` yields ``AsyncSession``
    - CLAUDE.md §8   — "Async by default for I/O"
"""

from __future__ import annotations

import uuid
from datetime import (
    datetime,  # noqa: TC003 — required at runtime by SQLAlchemy Mapped[] resolution
)
from typing import TYPE_CHECKING

from sqlalchemy import MetaData, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,  # noqa: TC002 — needed at runtime for mapped_column
    mapped_column,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from priormail.core.config import Settings

# Naming convention for constraints — makes Alembic autogenerate deterministic
# and avoids "index already exists" collisions.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Shared base for all ORM models."""

    metadata = metadata


class TimestampMixin:
    """Mixin that adds ``created_at`` and ``updated_at`` columns.

    ``created_at`` is set server-side on INSERT; ``updated_at`` is set on both
    INSERT and UPDATE.
    """

    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )


def new_uuid() -> uuid.UUID:
    """Generate a new UUID4 for use as a default PK value."""
    return uuid.uuid4()


def create_db_engine(
    settings: Settings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create the async engine and session factory from app settings.

    Called once during FastAPI lifespan startup. The engine must be disposed
    at shutdown (``await engine.dispose()``).
    """
    connect_args: dict[str, object] = {
        # Disable asyncpg's prepared-statement cache so connections work through
        # Supabase's PgBouncer pooler (port 6543, transaction mode) which does
        # not support named prepared statements.
        "prepared_statement_cache_size": 0,
    }
    if settings.database_ssl:
        connect_args["ssl"] = True

    engine = create_async_engine(
        settings.database_url,
        echo=(settings.environment == "development"),
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=5,  # burst headroom; total cap = pool_size + 5
        connect_args=connect_args,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, session_factory
