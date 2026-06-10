"""FastAPI dependency providers.

State is held on ``app.state`` and surfaced via ``Depends`` (no module-level
globals — CLAUDE.md §8). Tests override these providers to inject stubs.
"""

from __future__ import annotations

from fastapi import Request

from priormail.core.errors import ModelUnavailableError
from priormail.services.classifier import Classifier


def get_priority_classifier(request: Request) -> Classifier:
    """Return the loaded priority classifier, or 503 if unavailable."""
    classifier: Classifier | None = getattr(
        request.app.state, "priority_classifier", None
    )
    if classifier is None:
        raise ModelUnavailableError("Priority model is not loaded.")
    return classifier
