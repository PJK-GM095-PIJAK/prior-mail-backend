"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from priormail.models.schemas.envelope import success

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health/models")
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
