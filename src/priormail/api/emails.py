"""Emails API — list and retrieve synced emails.

Endpoints:
    GET /api/v1/emails       — paginated list (cursor-based)
    GET /api/v1/emails/{id}  — single email detail (logs access to audit_log)
"""

from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from priormail.core.deps import get_current_user, get_db
from priormail.core.errors import NotFoundError
from priormail.core.logging import get_logger
from priormail.models.orm.audit_log import AuditLog
from priormail.models.orm.email import Email
from priormail.models.orm.user import User
from priormail.models.schemas.envelope import Envelope, success

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/emails", tags=["emails"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class EmailSummary(BaseModel):
    """Lightweight email representation for list views."""

    id: str
    gmail_id: str
    thread_id: str | None = None
    subject: str | None = None
    snippet: str | None = None
    sender: str
    received_at: str
    is_read: bool
    labels: list[str] | None = None


class EmailDetail(EmailSummary):
    """Full email representation including body."""

    recipients: dict[str, list[str]] | None = None
    raw_body: str | None = None
    body_hash: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=Envelope[list[EmailSummary]])
async def list_emails(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, description="UUID of last email for pagination"),
) -> Envelope[list[EmailSummary]]:
    """Return a paginated list of the user's synced emails, newest first.

    Uses cursor-based pagination. Pass the ``id`` of the last email in the
    previous page as ``cursor`` to fetch the next page.
    """
    stmt = (
        select(Email)
        .where(Email.user_id == user.id)
        .order_by(Email.received_at.desc())
        .limit(limit)
    )

    if cursor:
        # Fetch the cursor email's received_at for keyset pagination.
        cursor_result = await session.execute(
            select(Email.received_at).where(
                Email.id == uuid_mod.UUID(cursor), Email.user_id == user.id
            )
        )
        cursor_date = cursor_result.scalar_one_or_none()
        if cursor_date is not None:
            stmt = stmt.where(Email.received_at < cursor_date)

    result = await session.execute(stmt)
    emails = list(result.scalars().all())

    items = [
        EmailSummary(
            id=str(e.id),
            gmail_id=e.gmail_id,
            thread_id=e.thread_id,
            subject=e.subject,
            snippet=e.snippet,
            sender=e.sender,
            received_at=e.received_at.isoformat(),
            is_read=e.is_read,
            labels=e.labels,
        )
        for e in emails
    ]

    meta: dict[str, object] = {"count": len(items)}
    if items:
        meta["next_cursor"] = items[-1].id

    return success(items, meta=meta)


@router.get("/{email_id}", response_model=Envelope[EmailDetail])
async def get_email(
    email_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Envelope[EmailDetail]:
    """Return a single email with full detail.

    Logs the access in ``audit_log`` as required by CLAUDE.md §9.
    """
    result = await session.execute(
        select(Email).where(
            Email.id == uuid_mod.UUID(email_id), Email.user_id == user.id
        )
    )
    email_row = result.scalar_one_or_none()
    if email_row is None:
        raise NotFoundError(f"Email {email_id} not found.")

    # Audit log — record email content access (CLAUDE.md §9).
    audit = AuditLog(
        user_id=user.id,
        action="email.body_read",
        resource_type="email",
        resource_id=email_row.id,
        metadata_={"snippet": (email_row.snippet or "")[:100]},
    )
    session.add(audit)
    await session.flush()

    return success(
        EmailDetail(
            id=str(email_row.id),
            gmail_id=email_row.gmail_id,
            thread_id=email_row.thread_id,
            subject=email_row.subject,
            snippet=email_row.snippet,
            sender=email_row.sender,
            recipients=email_row.recipients,
            received_at=email_row.received_at.isoformat(),
            is_read=email_row.is_read,
            labels=email_row.labels,
            raw_body=email_row.raw_body,
            body_hash=email_row.body_hash,
        )
    )
