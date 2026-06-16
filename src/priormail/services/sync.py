"""Email sync service — orchestrates Gmail → local DB synchronisation.

Handles both **full sync** (first-time, no history ID) and **delta sync**
(incremental via ``historyId``). Called by the sync API endpoint and
potentially by the background worker.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from priormail.core.errors import GmailApiError
from priormail.core.logging import get_logger
from priormail.models.orm.email import Email
from priormail.services.gmail_client import (
    fetch_history,
    fetch_message_detail,
    fetch_messages,
    get_user_profile,
    parse_message_headers,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from priormail.models.orm.user import User

logger = get_logger(__name__)


async def sync_emails(
    user: User,
    session: AsyncSession,
    *,
    max_results: int = 50,
) -> dict[str, object]:
    """Sync Gmail messages for the given user into the local DB.

    Returns a summary dict: ``{ "synced_count": int, "new_history_id": str }``.

    Raises :class:`GmailApiError` if the user has no Gmail token or if API
    calls fail.
    """
    refresh_token = user.gmail_token_enc
    if not refresh_token:
        raise GmailApiError("User has no Gmail refresh token. Connect Gmail first.")

    if user.gmail_history_id:
        return await _delta_sync(user, session, refresh_token)
    return await _full_sync(user, session, refresh_token, max_results=max_results)


async def _full_sync(
    user: User,
    session: AsyncSession,
    refresh_token: str,
    *,
    max_results: int = 50,
) -> dict[str, object]:
    """First-time sync: list recent messages and fetch their details."""
    logger.info("full_sync_start", user_id=str(user.id), max_results=max_results)

    # 1. List message stubs
    list_result = await fetch_messages(refresh_token, max_results=max_results)
    message_stubs: list[dict[str, str]] = list_result.get("messages", [])

    if not message_stubs:
        # No messages at all — just record the current history ID.
        profile = await get_user_profile(refresh_token)
        user.gmail_history_id = str(profile.get("historyId", ""))
        logger.info("full_sync_empty", user_id=str(user.id))
        return {"synced_count": 0, "new_history_id": user.gmail_history_id}

    # 2. Fetch details for each message
    synced = 0
    for stub in message_stubs:
        msg_id = stub["id"]

        # Skip if we already have this message
        exists = await session.execute(
            select(Email.id).where(
                Email.user_id == user.id, Email.gmail_id == msg_id
            )
        )
        if exists.scalar_one_or_none() is not None:
            continue

        raw_msg = await fetch_message_detail(refresh_token, msg_id)
        parsed = parse_message_headers(raw_msg)

        body_hash = None
        if parsed["raw_body"]:
            body_hash = hashlib.sha256(parsed["raw_body"].encode()).hexdigest()

        email_row = Email(
            user_id=user.id,
            gmail_id=parsed["gmail_id"],
            thread_id=parsed["thread_id"],
            subject=parsed["subject"],
            snippet=parsed["snippet"],
            sender=parsed["sender"],
            recipients=parsed["recipients"],
            received_at=parsed["received_at"],
            body_hash=body_hash,
            raw_body=parsed["raw_body"] or None,
            is_read=parsed["is_read"],
            labels=parsed["labels"],
        )
        session.add(email_row)
        synced += 1

    # 3. Update history ID from the profile
    profile = await get_user_profile(refresh_token)
    user.gmail_history_id = str(profile.get("historyId", ""))

    await session.flush()
    logger.info(
        "full_sync_done",
        user_id=str(user.id),
        synced_count=synced,
        history_id=user.gmail_history_id,
    )
    return {"synced_count": synced, "new_history_id": user.gmail_history_id}


async def _delta_sync(
    user: User,
    session: AsyncSession,
    refresh_token: str,
) -> dict[str, object]:
    """Incremental sync via Gmail ``history.list`` API."""
    assert user.gmail_history_id is not None  # noqa: S101 — caller guarantees
    logger.info(
        "delta_sync_start",
        user_id=str(user.id),
        history_id=user.gmail_history_id,
    )

    try:
        history_result = await fetch_history(refresh_token, user.gmail_history_id)
    except GmailApiError:
        # History ID expired (>7 days) — fall back to full sync.
        logger.warning("delta_sync_history_expired", user_id=str(user.id))
        user.gmail_history_id = None
        return await _full_sync(user, session, refresh_token)

    history_records: list[dict[str, Any]] = history_result.get("history", [])
    new_history_id = str(history_result.get("historyId", user.gmail_history_id))

    if not history_records:
        user.gmail_history_id = new_history_id
        logger.info("delta_sync_no_changes", user_id=str(user.id))
        return {"synced_count": 0, "new_history_id": new_history_id}

    # Collect unique new message IDs from history
    new_msg_ids: set[str] = set()
    for record in history_records:
        for msg in record.get("messagesAdded", []):
            msg_data = msg.get("message", {})
            mid = msg_data.get("id")
            if mid:
                new_msg_ids.add(mid)

    # Fetch and store new messages
    synced = 0
    for msg_id in new_msg_ids:
        exists = await session.execute(
            select(Email.id).where(
                Email.user_id == user.id, Email.gmail_id == msg_id
            )
        )
        if exists.scalar_one_or_none() is not None:
            continue

        raw_msg = await fetch_message_detail(refresh_token, msg_id)
        parsed = parse_message_headers(raw_msg)

        body_hash = None
        if parsed["raw_body"]:
            body_hash = hashlib.sha256(parsed["raw_body"].encode()).hexdigest()

        email_row = Email(
            user_id=user.id,
            gmail_id=parsed["gmail_id"],
            thread_id=parsed["thread_id"],
            subject=parsed["subject"],
            snippet=parsed["snippet"],
            sender=parsed["sender"],
            recipients=parsed["recipients"],
            received_at=parsed["received_at"],
            body_hash=body_hash,
            raw_body=parsed["raw_body"] or None,
            is_read=parsed["is_read"],
            labels=parsed["labels"],
        )
        session.add(email_row)
        synced += 1

    user.gmail_history_id = new_history_id
    await session.flush()
    logger.info(
        "delta_sync_done",
        user_id=str(user.id),
        synced_count=synced,
        history_id=new_history_id,
    )
    return {"synced_count": synced, "new_history_id": new_history_id}
