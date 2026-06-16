"""Gmail API client — thin async wrapper around ``google-api-python-client``.

All Google API calls are synchronous under the hood, so every public function
in this module runs the blocking call inside ``asyncio.to_thread`` to keep the
event loop free (CLAUDE.md §8, §10).

Scope: ``gmail.readonly`` only — no send, no modify (CLAUDE.md §9).
"""

from __future__ import annotations

import asyncio
import base64
import email.utils
from datetime import UTC, datetime
from typing import Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from priormail.core.config import get_settings
from priormail.core.errors import GmailApiError
from priormail.core.logging import get_logger

logger = get_logger(__name__)

# MVP scope — read-only access to Gmail (CLAUDE.md §9).
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Google's OAuth2 token endpoint.
_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _build_flow(redirect_uri: str | None = None) -> Flow:
    """Build a Google OAuth2 flow from app settings."""
    settings = get_settings()
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": _TOKEN_URI,
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=GMAIL_SCOPES)
    flow.redirect_uri = redirect_uri or settings.google_redirect_uri
    return flow


async def exchange_code_for_tokens(
    code: str, redirect_uri: str | None = None
) -> dict[str, Any]:
    """Exchange an authorization code for access + refresh tokens.

    Returns the full token dict from Google (contains ``access_token``,
    ``refresh_token``, ``token_uri``, etc.).

    Raises :class:`GmailApiError` on failure.
    """

    def _exchange() -> dict[str, Any]:
        flow = _build_flow(redirect_uri)
        flow.fetch_token(code=code)
        creds = flow.credentials
        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or []),
        }

    try:
        return await asyncio.to_thread(_exchange)
    except Exception as exc:
        logger.error("gmail_token_exchange_failed", error=str(exc))
        raise GmailApiError(f"Failed to exchange authorization code: {exc}") from exc


def _build_credentials(refresh_token: str) -> Credentials:
    """Build Google credentials from a stored refresh token."""
    settings = get_settings()
    return Credentials(  # type: ignore[no-untyped-call]
        token=None,
        refresh_token=refresh_token,
        token_uri=_TOKEN_URI,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=GMAIL_SCOPES,
    )


def _build_gmail_service(credentials: Credentials) -> Any:
    """Build a Gmail API service resource (synchronous)."""
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


async def get_user_profile(refresh_token: str) -> dict[str, Any]:
    """Fetch the authenticated user's Gmail profile (email, display name).

    Returns ``{ "emailAddress": "...", "messagesTotal": ..., "historyId": "..." }``.
    """

    def _fetch() -> dict[str, Any]:
        creds = _build_credentials(refresh_token)
        service = _build_gmail_service(creds)
        return service.users().getProfile(userId="me").execute()  # type: ignore[no-any-return]

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as exc:
        logger.error("gmail_profile_fetch_failed", error=str(exc))
        raise GmailApiError(f"Failed to fetch Gmail profile: {exc}") from exc


async def fetch_messages(
    refresh_token: str,
    *,
    max_results: int = 50,
    page_token: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """List message stubs (id + threadId only) from the user's mailbox.

    Returns the raw ``messages.list`` response (may contain ``nextPageToken``).
    """

    def _list() -> dict[str, Any]:
        creds = _build_credentials(refresh_token)
        service = _build_gmail_service(creds)
        kwargs: dict[str, Any] = {"userId": "me", "maxResults": max_results}
        if page_token:
            kwargs["pageToken"] = page_token
        if query:
            kwargs["q"] = query
        return service.users().messages().list(**kwargs).execute()  # type: ignore[no-any-return]

    try:
        return await asyncio.to_thread(_list)
    except Exception as exc:
        logger.error("gmail_messages_list_failed", error=str(exc))
        raise GmailApiError(f"Failed to list Gmail messages: {exc}") from exc


async def fetch_message_detail(
    refresh_token: str, msg_id: str
) -> dict[str, Any]:
    """Fetch a single message in ``full`` format (headers + body parts)."""

    def _get() -> dict[str, Any]:
        creds = _build_credentials(refresh_token)
        service = _build_gmail_service(creds)
        return (  # type: ignore[no-any-return]
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )

    try:
        return await asyncio.to_thread(_get)
    except Exception as exc:
        logger.error("gmail_message_get_failed", msg_id=msg_id, error=str(exc))
        raise GmailApiError(f"Failed to fetch message {msg_id}: {exc}") from exc


async def fetch_history(
    refresh_token: str, start_history_id: str
) -> dict[str, Any]:
    """Fetch history records since ``start_history_id`` for delta sync.

    Returns the raw ``history.list`` response.
    """

    def _history() -> dict[str, Any]:
        creds = _build_credentials(refresh_token)
        service = _build_gmail_service(creds)
        return (  # type: ignore[no-any-return]
            service.users()
            .history()
            .list(userId="me", startHistoryId=start_history_id)
            .execute()
        )

    try:
        return await asyncio.to_thread(_history)
    except Exception as exc:
        logger.error("gmail_history_failed", error=str(exc))
        raise GmailApiError(f"Failed to fetch Gmail history: {exc}") from exc


# ---------------------------------------------------------------------------
# Message parsing helpers
# ---------------------------------------------------------------------------


def parse_message_headers(
    raw_message: dict[str, Any],
) -> dict[str, Any]:
    """Extract useful fields from a Gmail API ``messages.get`` response.

    Returns a flat dict with keys: ``gmail_id``, ``thread_id``, ``subject``,
    ``sender``, ``recipients``, ``received_at``, ``snippet``, ``is_read``,
    ``labels``, ``raw_body``.
    """
    headers: dict[str, str] = {}
    for hdr in raw_message.get("payload", {}).get("headers", []):
        name: str = hdr.get("name", "").lower()
        if name in ("from", "to", "cc", "bcc", "subject", "date"):
            headers[name] = hdr.get("value", "")

    # Parse date
    date_str = headers.get("date", "")
    try:
        parsed_date = email.utils.parsedate_to_datetime(date_str)
        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        parsed_date = datetime.now(tz=UTC)

    # Parse body
    raw_body = _extract_body(raw_message.get("payload", {}))

    # Labels & read status
    label_ids: list[str] = raw_message.get("labelIds", [])
    is_read = "UNREAD" not in label_ids

    return {
        "gmail_id": raw_message.get("id", ""),
        "thread_id": raw_message.get("threadId"),
        "subject": headers.get("subject"),
        "sender": headers.get("from", "unknown@unknown"),
        "recipients": {
            "to": [a.strip() for a in headers.get("to", "").split(",") if a.strip()],
            "cc": [a.strip() for a in headers.get("cc", "").split(",") if a.strip()],
            "bcc": [a.strip() for a in headers.get("bcc", "").split(",") if a.strip()],
        },
        "received_at": parsed_date,
        "snippet": raw_message.get("snippet", "")[:200],
        "is_read": is_read,
        "labels": label_ids,
        "raw_body": raw_body,
    }


def _extract_body(payload: dict[str, Any]) -> str:
    """Recursively extract the plain-text body from a message payload."""
    mime_type = payload.get("mimeType", "")

    # Single-part message
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    # Multipart — recurse into parts
    for part in payload.get("parts", []):
        body = _extract_body(part)
        if body:
            return body

    return ""
