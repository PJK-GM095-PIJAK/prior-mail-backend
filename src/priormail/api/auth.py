"""Auth API — Google OAuth callback and user profile.

Endpoints:
    POST /api/v1/auth/google/callback — exchange auth code for tokens
    GET  /api/v1/auth/me              — current user profile
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from priormail.core.deps import get_current_user, get_current_user_id, get_db
from priormail.core.logging import get_logger
from priormail.models.orm.user import User
from priormail.models.schemas.auth import (
    AuthTokenResponse,
    GoogleCallbackRequest,
    UserProfile,
)
from priormail.models.schemas.envelope import Envelope, success
from priormail.services.gmail_client import exchange_code_for_tokens, get_user_profile

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/google/callback", response_model=Envelope[AuthTokenResponse])
async def google_callback(
    payload: GoogleCallbackRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> Envelope[AuthTokenResponse]:
    """Exchange a Google authorization code for tokens and link Gmail.

    The frontend obtains an auth code from Google's consent screen, then sends
    it here. The backend exchanges it for access + refresh tokens, stores the
    encrypted refresh token on the user row, and returns connection status.

    Requires a valid Supabase JWT in the ``Authorization`` header.
    """
    import uuid

    from sqlalchemy import select

    # 1. Exchange auth code → tokens
    tokens = await exchange_code_for_tokens(
        payload.code, redirect_uri=payload.redirect_uri
    )
    refresh_token: str | None = tokens.get("refresh_token")
    if not refresh_token:
        from priormail.core.errors import GmailApiError

        raise GmailApiError("Google did not return a refresh token. Try re-authorizing.")

    # 2. Fetch Gmail profile to get the user's email
    profile = await get_user_profile(refresh_token)
    gmail_email: str = profile.get("emailAddress", "")

    # 3. Upsert user record
    uid = uuid.UUID(user_id)
    result = await session.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            id=uid,
            email=gmail_email,
            gmail_token_enc=refresh_token,
            gmail_history_id=str(profile.get("historyId", "")),
        )
        session.add(user)
    else:
        user.email = gmail_email
        user.gmail_token_enc = refresh_token
        user.gmail_history_id = str(profile.get("historyId", ""))

    await session.flush()

    logger.info(
        "gmail_connected",
        user_id=user_id,
        email=gmail_email,
    )

    return success(
        AuthTokenResponse(
            gmail_connected=True,
            email=gmail_email,
            display_name=user.display_name,
        )
    )


@router.get("/me", response_model=Envelope[UserProfile])
async def get_me(
    user: User = Depends(get_current_user),
) -> Envelope[UserProfile]:
    """Return the current user's profile and Gmail connection status.

    Requires a valid Supabase JWT in the ``Authorization`` header.
    """
    return success(
        UserProfile(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            gmail_connected=user.gmail_token_enc is not None,
        )
    )
