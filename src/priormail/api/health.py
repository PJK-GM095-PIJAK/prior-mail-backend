"""Health endpoints (API_CONTRACT.md §3)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from priormail.models.schemas.envelope import success

router = APIRouter(prefix="/api/v1", tags=["health"])

limiter = Limiter(key_func=get_remote_address)


@router.get("/health")
@limiter.limit("600/hour")
async def health(request: Request):
    """Basic liveness check. Returns 200 if the app is up."""
    return success({"status": "ok"})


@router.get("/health/models")
@limiter.limit("600/hour")
async def health_models(request: Request):
    """Report loaded model versions."""
    classifier = getattr(request.app.state, "priority_classifier", None)
    phishing = getattr(request.app.state, "phishing_model", None)
    return success({
        "priority_classifier": {
            "status": "loaded" if classifier else "unavailable",
            "version": classifier.version if classifier else None,
        },
        "phishing_detector": {
            "status": "loaded" if phishing else "unavailable",
        },
    })
