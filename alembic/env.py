"""Alembic environment configuration.

Loads DATABASE_URL from priormail Settings, imports all ORM models so
autogenerate can detect tables, and runs migrations asynchronously via asyncpg.

See also:
    - core/config.py     → DATABASE_URL
    - models/db.py       → Base metadata
    - models/__init__.py  → registers all ORM models
    - CLAUDE.md §8       → migration rules
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from priormail.core.config import get_settings

# Import all models so Base.metadata contains every table for autogenerate.
from priormail.models import Base  # noqa: F401 — side-effect import

# Alembic Config object — provides access to values in alembic.ini.
config = context.config

# Interpret the config file for Python logging (if present).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from app settings (never hardcode secrets in ini).
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Target metadata for autogenerate support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live connection).

    Calls ``context.execute()`` with the literal SQL instead of executing it.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    """Configure context and run migrations within a connection."""
    context.configure(connection=connection, target_metadata=target_metadata)  # type: ignore[arg-type]
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
