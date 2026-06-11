"""Initial schema — users, emails, prioritization_results, extracted_tasks, audit_log.

Revision ID: 0001
Revises: —
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create all initial tables."""

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(2048), nullable=True),
        sa.Column("gmail_token_enc", sa.Text(), nullable=True),
        sa.Column("gmail_history_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # --- emails ---
    op.create_table(
        "emails",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("gmail_id", sa.String(64), nullable=False),
        sa.Column("thread_id", sa.String(64), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("snippet", sa.String(200), nullable=True),
        sa.Column("sender", sa.String(320), nullable=False),
        sa.Column("recipients", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("body_hash", sa.String(64), nullable=True),
        sa.Column("raw_body", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_emails"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_emails_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "uq_emails_user_gmail", "emails", ["user_id", "gmail_id"], unique=True
    )
    op.create_index(
        "ix_emails_user_received", "emails", ["user_id", "received_at"]
    )

    # --- prioritization_results ---
    op.create_table(
        "prioritization_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email_id", sa.Uuid(), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("is_phishing", sa.Boolean(), nullable=True),
        sa.Column("phishing_score", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_prioritization_results"),
        sa.ForeignKeyConstraint(
            ["email_id"],
            ["emails.id"],
            name="fk_prioritization_results_email_id_emails",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_prioritization_email_id",
        "prioritization_results",
        ["email_id"],
    )

    # --- extracted_tasks ---
    op.create_table(
        "extracted_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_extracted_tasks"),
        sa.ForeignKeyConstraint(
            ["email_id"],
            ["emails.id"],
            name="fk_extracted_tasks_email_id_emails",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_extracted_tasks_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_tasks_user_completed",
        "extracted_tasks",
        ["user_id", "is_completed"],
    )

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_audit_log_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_audit_user_created", "audit_log", ["user_id", "created_at"]
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("audit_log")
    op.drop_table("extracted_tasks")
    op.drop_table("prioritization_results")
    op.drop_table("emails")
    op.drop_table("users")
