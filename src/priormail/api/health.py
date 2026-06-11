"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from priormail.core.deps import get_db, get_priority_classifier
from priormail.models.schemas.envelope import Envelope, success
from priormail.services.classifier import Classifier

router = APIRouter(prefix="/api/v1/_health", tags=["health"])


@router.get("/models", response_model=Envelope[dict[str, str]])
def model_health(
    classifier: Classifier = Depends(get_priority_classifier),
) -> Envelope[dict[str, str]]:
    """Report loaded model versions (BACKEND_INTEGRATION_GUIDE §2).

    503 (``service.model_unavailable``) if a model failed to load.
    """
    return success({"priority": classifier.version})


@router.get("/db", response_model=Envelope[dict[str, str]])
async def db_health(
    session: AsyncSession = Depends(get_db),
) -> Envelope[dict[str, str]]:
    """Verify database connectivity.

    Runs a simple ``SELECT 1`` query. Returns 503 (``service.database_error``)
    if the database is unreachable.
    """
    await session.execute(text("SELECT 1"))
    return success({"status": "connected"})
