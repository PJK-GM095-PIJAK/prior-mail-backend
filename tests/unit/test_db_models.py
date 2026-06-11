"""Unit tests for ORM model definitions.

These tests validate model structure (columns, types, constraints, indexes)
without requiring a live database connection.
"""

from __future__ import annotations

import uuid

from priormail.models.orm.audit_log import AuditLog
from priormail.models.orm.db import Base, new_uuid
from priormail.models.orm.email import Email
from priormail.models.orm.prioritization import PrioritizationResult
from priormail.models.orm.task import ExtractedTask
from priormail.models.orm.user import User


class TestBase:
    """Tests for the shared declarative base and mixins."""

    def test_base_has_naming_convention(self) -> None:
        assert "fk" in Base.metadata.naming_convention
        assert "uq" in Base.metadata.naming_convention
        assert "pk" in Base.metadata.naming_convention

    def test_new_uuid_returns_uuid4(self) -> None:
        result = new_uuid()
        assert isinstance(result, uuid.UUID)
        assert result.version == 4

    def test_new_uuid_is_unique(self) -> None:
        ids = {new_uuid() for _ in range(100)}
        assert len(ids) == 100


class TestTimestampMixin:
    """Tests for the timestamp mixin columns."""

    def test_user_has_timestamps(self) -> None:
        """User uses TimestampMixin — verify columns exist."""
        table = User.__table__
        assert "created_at" in table.columns
        assert "updated_at" in table.columns

    def test_email_has_timestamps(self) -> None:
        table = Email.__table__
        assert "created_at" in table.columns
        assert "updated_at" in table.columns


class TestUserModel:
    """Tests for the User ORM model."""

    def test_tablename(self) -> None:
        assert User.__tablename__ == "users"

    def test_required_columns(self) -> None:
        table = User.__table__
        col_names = {c.name for c in table.columns}
        expected = {
            "id", "email", "display_name", "avatar_url",
            "gmail_token_enc", "gmail_history_id",
            "created_at", "updated_at",
        }
        assert expected.issubset(col_names)

    def test_email_is_unique(self) -> None:
        table = User.__table__
        email_col = table.columns["email"]
        assert email_col.unique is True

    def test_id_is_uuid_primary_key(self) -> None:
        table = User.__table__
        id_col = table.columns["id"]
        assert id_col.primary_key is True

    def test_repr(self) -> None:
        user = User(id=uuid.uuid4(), email="test@example.com")
        user.email = "test@example.com"
        r = repr(user)
        assert "User" in r
        assert "test@example.com" in r


class TestEmailModel:
    """Tests for the Email ORM model."""

    def test_tablename(self) -> None:
        assert Email.__tablename__ == "emails"

    def test_required_columns(self) -> None:
        table = Email.__table__
        col_names = {c.name for c in table.columns}
        expected = {
            "id", "user_id", "gmail_id", "thread_id", "subject", "snippet",
            "sender", "recipients", "received_at", "body_hash", "raw_body",
            "is_read", "labels", "created_at", "updated_at",
        }
        assert expected.issubset(col_names)

    def test_has_user_foreign_key(self) -> None:
        table = Email.__table__
        fk_cols = {fk.parent.name for fk in table.foreign_keys}
        assert "user_id" in fk_cols

    def test_has_composite_unique_index(self) -> None:
        table = Email.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "uq_emails_user_gmail" in index_names

    def test_has_received_at_index(self) -> None:
        table = Email.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_emails_user_received" in index_names


class TestPrioritizationResultModel:
    """Tests for the PrioritizationResult ORM model."""

    def test_tablename(self) -> None:
        assert PrioritizationResult.__tablename__ == "prioritization_results"

    def test_required_columns(self) -> None:
        table = PrioritizationResult.__table__
        col_names = {c.name for c in table.columns}
        expected = {
            "id", "email_id", "priority", "confidence", "model_version",
            "is_phishing", "phishing_score", "summary",
            "created_at", "updated_at",
        }
        assert expected.issubset(col_names)

    def test_nullable_phishing_fields(self) -> None:
        table = PrioritizationResult.__table__
        assert table.columns["is_phishing"].nullable is True
        assert table.columns["phishing_score"].nullable is True
        assert table.columns["summary"].nullable is True

    def test_has_email_foreign_key(self) -> None:
        table = PrioritizationResult.__table__
        fk_cols = {fk.parent.name for fk in table.foreign_keys}
        assert "email_id" in fk_cols


class TestExtractedTaskModel:
    """Tests for the ExtractedTask ORM model."""

    def test_tablename(self) -> None:
        assert ExtractedTask.__tablename__ == "extracted_tasks"

    def test_required_columns(self) -> None:
        table = ExtractedTask.__table__
        col_names = {c.name for c in table.columns}
        expected = {
            "id", "email_id", "user_id", "title", "description",
            "due_date", "is_completed", "completed_at",
            "created_at", "updated_at",
        }
        assert expected.issubset(col_names)

    def test_has_both_foreign_keys(self) -> None:
        table = ExtractedTask.__table__
        fk_cols = {fk.parent.name for fk in table.foreign_keys}
        assert "email_id" in fk_cols
        assert "user_id" in fk_cols

    def test_has_user_completed_index(self) -> None:
        table = ExtractedTask.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_tasks_user_completed" in index_names


class TestAuditLogModel:
    """Tests for the AuditLog ORM model."""

    def test_tablename(self) -> None:
        assert AuditLog.__tablename__ == "audit_log"

    def test_required_columns(self) -> None:
        table = AuditLog.__table__
        col_names = {c.name for c in table.columns}
        expected = {
            "id", "user_id", "action", "resource_type",
            "resource_id", "metadata", "created_at",
        }
        assert expected.issubset(col_names)

    def test_no_updated_at(self) -> None:
        """Audit log is append-only — no updated_at column."""
        table = AuditLog.__table__
        assert "updated_at" not in {c.name for c in table.columns}

    def test_has_user_created_index(self) -> None:
        table = AuditLog.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_audit_user_created" in index_names

    def test_has_user_foreign_key(self) -> None:
        table = AuditLog.__table__
        fk_cols = {fk.parent.name for fk in table.foreign_keys}
        assert "user_id" in fk_cols


class TestAllModelsRegistered:
    """Verify all models are discoverable via Base.metadata."""

    def test_all_tables_in_metadata(self) -> None:
        table_names = set(Base.metadata.tables.keys())
        expected = {
            "users", "emails", "prioritization_results",
            "extracted_tasks", "audit_log",
        }
        assert expected.issubset(table_names)
