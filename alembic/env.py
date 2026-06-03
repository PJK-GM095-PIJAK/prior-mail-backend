# alembic/env.py
# ─────────────────────────────────────────────────────────────
# Alembic environment configuration.
#
# Responsibilities:
# - Load database URL from priormail Settings (pydantic-settings)
# - Import all SQLAlchemy models so autogenerate works
# - Configure async migration runner
#
# Pattern:
#   from priormail.core.config import settings
#   from priormail.models.db import Base
#
#   config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
#   target_metadata = Base.metadata
#
# Notes:
# - Uses async engine for migrations (asyncpg)
# - Migration filenames: YYYYMMDD_HHMM_<description>.py
# - Always include downgrade(), even if it's just pass
# - NEVER modify an already-applied migration
#
# See also:
#   - core/config.py     → DATABASE_URL
#   - models/db.py       → Base metadata
#   - CLAUDE.md §8       → migration rules
# ─────────────────────────────────────────────────────────────
