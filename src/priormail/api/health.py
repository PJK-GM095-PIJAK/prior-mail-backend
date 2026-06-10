"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from priormail.core.deps import get_priority_classifier
from priormail.models.envelope import Envelope, success
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
