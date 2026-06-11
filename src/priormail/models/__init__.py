"""Models — SQLAlchemy ORM models, Pydantic schemas, and shared enums.

Importing this package registers all ORM models with :class:`Base.metadata`,
which is required for Alembic autogenerate to detect tables.
"""

from priormail.models.orm.audit_log import AuditLog
from priormail.models.orm.db import Base
from priormail.models.orm.email import Email
from priormail.models.orm.prioritization import PrioritizationResult
from priormail.models.orm.task import ExtractedTask
from priormail.models.orm.user import User

__all__ = [
    "AuditLog",
    "Base",
    "Email",
    "ExtractedTask",
    "PrioritizationResult",
    "User",
]
