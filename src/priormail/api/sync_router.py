"""Sync API — trigger a manual Gmail sync for the current user.

Endpoint:
    POST /api/v1/sync — synchronise Gmail → local DB
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from priormail.core.deps import get_current_user, get_db
from priormail.models.orm.user import User
from priormail.models.schemas.envelope import Envelope, success
from priormail.services.sync import sync_emails

router = APIRouter(prefix="/api/v1", tags=["sync"])


class SyncResponse(Envelope[dict[str, object]]):
    """Typed alias for the sync response envelope."""


@router.post("/sync", response_model=Envelope[dict[str, object]])
async def trigger_sync(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Envelope[dict[str, object]]:
    """Trigger a manual email sync for the authenticated user.

    Performs a full sync if this is the first time, or a delta sync using the
    stored ``gmail_history_id``. Returns the count of newly synced emails and
    the updated history ID.

    Requires a valid Supabase JWT and a connected Gmail account.
    """
    result = await sync_emails(user, session)
    return success(result)
