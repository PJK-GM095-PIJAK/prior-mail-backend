"""FastAPI dependency providers.

State is held on ``app.state`` and surfaced via ``Depends`` (no module-level
globals — CLAUDE.md §8). Tests override these providers to inject stubs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from priormail.core.errors import ModelUnavailableError
from priormail.services.classifier import Classifier

if TYPE_CHECKING:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer


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
