"""FastAPI dependency providers.

State is held on ``app.state`` and surfaced via ``Depends`` (no module-level
globals — CLAUDE.md §8). Tests override these providers to inject stubs.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from priormail.core.errors import (
    AuthenticationError,
    DatabaseError,
    ModelUnavailableError,
)
from priormail.models.orm.user import User
from priormail.services.classifier import Classifier

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Reusable security scheme — extracts ``Authorization: Bearer <token>`` from
# the request header. ``auto_error=False`` so we can return our own typed error.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_priority_classifier(request: Request) -> Classifier:
    """Return the loaded priority classifier, or 503 if unavailable."""
    classifier: Classifier | None = getattr(
        request.app.state, "priority_classifier", None
    )
    if classifier is None:
        raise ModelUnavailableError("Priority model is not loaded.")
    return classifier


def get_phishing_classifier(
    request: Request,
) -> tuple[AutoModelForSequenceClassification, AutoTokenizer]:
    """Return the loaded phishing model and tokenizer, or raise 503 if unavailable."""
    model = getattr(request.app.state, "phishing_model", None)
    tokenizer = getattr(request.app.state, "phishing_tokenizer", None)
    if model is None or tokenizer is None:
        raise ModelUnavailableError("Phishing model is not loaded.")
    return model, tokenizer


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session scoped to the request.

    The session is committed on success and rolled back on exception, then
    always closed. Raises :class:`DatabaseError` if no session factory is
    available (i.e. the app started without a DB).
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "db_session_factory", None
    )
    if factory is None:
        raise DatabaseError("Database session factory is not initialised.")

    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Validate the Supabase JWT and return the user UUID (``sub`` claim).

    Lightweight dependency — no DB access. Raises :class:`AuthenticationError`
    on missing / expired / invalid tokens.
    """
    from jose import JWTError, jwt

    from priormail.core.config import get_settings

    if credentials is None:
        raise AuthenticationError("Missing Authorization header.")

    token = credentials.credentials
    settings = get_settings()

    try:
        payload: dict[str, object] = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError as exc:
        raise AuthenticationError(f"Invalid or expired token: {exc}") from exc

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AuthenticationError("Token is missing 'sub' claim.")

    return sub


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Validate JWT, look up (or upsert) the user, and return the ORM object.

    Combines JWT validation with a DB lookup. A ``User`` row is created on
    first access if it does not exist yet (the UUID comes from Supabase Auth).
    """
    from sqlalchemy import select

    uid = uuid.UUID(user_id)
    result = await session.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if user is None:
        # First time this Supabase Auth user hits the backend — create a stub
        # row. Email is populated when the Google OAuth callback runs.
        user = User(id=uid, email=f"{user_id}@pending")
        session.add(user)
        await session.flush()

    return user
