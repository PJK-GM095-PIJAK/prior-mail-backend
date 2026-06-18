"""Shared test fixtures for PriorMail backend tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from priormail.core.deps import get_priority_classifier
from priormail.main import create_app
from priormail.services.classifier import Prediction

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


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

    def classify(self, subject: str | None, body: str | None) -> Prediction:
        """Convenience wrapper matching PriorityClassifier.classify."""
        return Prediction(label=self._label, confidence=self._confidence)


class StubGroqClient:
    """Fake Groq client that returns canned LLM responses."""

    def __init__(
        self,
        summary: str = "This is a test summary.",
        tasks_json: str = '[{"description": "Prepare report", "due_date": null}]',
    ) -> None:
        self._summary = summary
        self._tasks_json = tasks_json
        self._call_count = 0
        self.chat = self  # noqa: PLW0642
        self.completions = self  # noqa: PLW0642

    def create(self, **_kwargs: Any) -> Any:
        """Return a mock response matching the Groq SDK shape."""
        self._call_count += 1
        # First call = summarize, second call = extract_tasks
        content = self._summary if self._call_count == 1 else self._tasks_json
        message = MagicMock()
        message.content = content
        choice = MagicMock()
        choice.message = message
        response = MagicMock()
        response.choices = [choice]
        return response


class StubPhishingModel:
    """Fake phishing model that always returns not-phishing."""

    def __call__(self, **kwargs: Any) -> Any:
        import torch

        logits = torch.tensor([[2.0, -2.0]])  # class 0 = not phishing
        result = MagicMock()
        result.logits = logits
        return result

    def eval(self) -> None:
        pass


class StubPhishingTokenizer:
    """Fake tokenizer that returns dummy tensors."""

    def __call__(self, text: str, **kwargs: Any) -> dict[str, Any]:
        import torch

        return {"input_ids": torch.zeros(1, 10, dtype=torch.long)}


# ---------------------------------------------------------------------------
# Fixtures — shared
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_eml_bytes() -> bytes:
    """Read the sample.eml fixture file as bytes."""
    return (FIXTURES_DIR / "sample.eml").read_bytes()


@pytest.fixture
def stub_classifier() -> StubClassifier:
    return StubClassifier()


@pytest.fixture
def stub_groq() -> StubGroqClient:
    return StubGroqClient()


@pytest.fixture
def stub_phishing_model() -> StubPhishingModel:
    return StubPhishingModel()


@pytest.fixture
def stub_phishing_tokenizer() -> StubPhishingTokenizer:
    return StubPhishingTokenizer()


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


@pytest.fixture
def app_with_pipeline(
    stub_classifier: StubClassifier,
    stub_groq: StubGroqClient,
    stub_phishing_model: StubPhishingModel,
    stub_phishing_tokenizer: StubPhishingTokenizer,
) -> FastAPI:
    """App with a fully-stubbed pipeline wired into app.state."""
    from priormail.agents.graph import build_graph

    application = create_app()
    application.state.priority_classifier = stub_classifier
    application.state.phishing_model = stub_phishing_model
    application.state.phishing_tokenizer = stub_phishing_tokenizer
    application.state.pipeline = build_graph(
        priority_classifier=stub_classifier,
        phishing_model=stub_phishing_model,
        phishing_tokenizer=stub_phishing_tokenizer,
        phishing_version="v-test-phishing",
        llm_client=stub_groq,
    )
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def pipeline_client(app_with_pipeline: FastAPI) -> AsyncIterator[AsyncClient]:
    """HTTP client wired to an app with a fully-stubbed pipeline."""
    transport = ASGITransport(app=app_with_pipeline)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
