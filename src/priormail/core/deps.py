"""FastAPI dependency providers.

State is held on ``app.state`` and surfaced via ``Depends`` (no module-level
globals — CLAUDE.md §8). Tests override these providers to inject stubs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from priormail.core.errors import DatabaseError, ModelUnavailableError
from priormail.services.classifier import Classifier

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    from sqlalchemy.ext.asyncio import AsyncSession


def get_priority_classifier(request: Request) -> Classifier:
    """Return the loaded priority classifier, or 503 if unavailable."""
    classifier: Classifier | None = getattr(
        request.app.state, "priority_classifier", None
    )
    if classifier is None:
        raise ModelUnavailableError("Priority model is not loaded.")
    return classifier


def get_phishing_classifier(request: Request) -> tuple[AutoModelForSequenceClassification, AutoTokenizer]:
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
