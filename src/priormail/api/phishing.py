# src/priormail/api/phishing.py
"""Phishing detection endpoint.
Provides a simple POST that returns whether the email is phishing and the confidence score.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request

from priormail.core.deps import get_phishing_classifier
from priormail.models.schemas.envelope import Envelope, success
from priormail.models.schemas.phishing import PhishingData
from priormail.services.phishing_inference import predict_phishing

router = APIRouter(prefix="/api/v1/classify", tags=["phishing"])


@router.post("/phishing", response_model=Envelope[PhishingData])
async def classify_phishing(
    request: Request,
    deps: tuple = Depends(get_phishing_classifier),
) -> Envelope[PhishingData]:
    """Classify the given text as phishing or not.
    The request body must contain either ``subject`` or ``body`` (same schema as priority).
    For simplicity we reuse the priority request schema via ``request.json()``.
    """
    payload = await request.json()
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    # Build a simple text input – reuse the same helper as priority classification.
    from priormail.services.preprocess import build_priority_input

    text = build_priority_input(subject, body)
    model, tokenizer = deps
    is_phish, score = await asyncio.to_thread(predict_phishing, model, tokenizer, text)
    return success(
        PhishingData(is_phishing=is_phish, phishing_score=score)
    )
