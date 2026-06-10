"""Priority classification endpoint.

Standalone classify slice used by the frontend while the full emails/reclassify
flow (API_CONTRACT.md §4) is not yet built. Not part of the authoritative
contract — see the integration plan's follow-ups.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from priormail.core.deps import get_priority_classifier
from priormail.models.envelope import Envelope, success
from priormail.models.priority import ClassifyData, ClassifyRequest
from priormail.services.classifier import Classifier
from priormail.services.preprocess import build_priority_input

router = APIRouter(prefix="/api/v1/classify", tags=["classify"])


@router.post("/priority", response_model=Envelope[ClassifyData])
async def classify_priority(
    payload: ClassifyRequest,
    classifier: Classifier = Depends(get_priority_classifier),
) -> Envelope[ClassifyData]:
    """Classify an email's priority from its subject and body."""
    text = build_priority_input(payload.subject, payload.body)
    # Inference is CPU-bound; offload so the event loop isn't blocked (CLAUDE.md §10).
    predictions = await asyncio.to_thread(classifier.predict, [text])
    prediction = predictions[0]
    return success(
        ClassifyData(
            priority=prediction.label,
            priority_confidence=prediction.confidence,
            model_version=classifier.version,
        )
    )
