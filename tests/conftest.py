"""Shared test fixtures for PriorMail backend tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from priormail.core.deps import get_priority_classifier
from priormail.main import create_app
from priormail.services.classifier import Prediction

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI


class StubClassifier:
    """In-memory classifier implementing the Classifier protocol (no model load)."""

    version = "v-test"

    def __init__(self, label: str = "urgent", confidence: float = 0.91) -> None:
        self._label = label
        self._confidence = confidence
        self.calls: list[list[str]] = []

    def predict(self, inputs: list[str]) -> list[Prediction]:
        self.calls.append(inputs)
        return [
            Prediction(label=self._label, confidence=self._confidence) for _ in inputs
        ]


@pytest.fixture
def stub_classifier() -> StubClassifier:
    return StubClassifier()


@pytest.fixture
def app(stub_classifier: StubClassifier) -> FastAPI:
    """App with the classifier dependency overridden to a stub (no real model)."""
    application = create_app()
    application.dependency_overrides[get_priority_classifier] = lambda: stub_classifier
    return application


@pytest.fixture
def app_without_model() -> FastAPI:
    """App with no model loaded and no override (exercises the 503 path)."""
    return create_app()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
