"""Unit tests for the classify_priority agent node."""

from __future__ import annotations

from priormail.agents.classify import classify_priority
from priormail.agents.state import PipelineState
from priormail.services.classifier import Prediction


class _StubClassifier:
    """Minimal stub matching the Classifier protocol."""

    version = "v2.0"

    def __init__(self, label: str = "normal", confidence: float = 0.85) -> None:
        self._label = label
        self._confidence = confidence

    def classify(self, subject: str | None, body: str | None) -> Prediction:
        return Prediction(label=self._label, confidence=self._confidence)


class TestClassifyPriority:
    def test_returns_label_and_confidence(self) -> None:
        clf = _StubClassifier(label="urgent", confidence=0.92)
        state = PipelineState(subject="URGENT", body_text="Please approve ASAP")
        result = classify_priority(state, clf)
        assert result["priority"] == "urgent"
        assert result["priority_confidence"] == 0.92
        assert result["priority_model_version"] == "v2.0"

    def test_low_priority(self) -> None:
        clf = _StubClassifier(label="low", confidence=0.75)
        state = PipelineState(subject="Newsletter", body_text="Weekly digest")
        result = classify_priority(state, clf)
        assert result["priority"] == "low"

    def test_version_exposed(self) -> None:
        clf = _StubClassifier()
        state = PipelineState(subject="X", body_text="Y")
        result = classify_priority(state, clf)
        assert result["priority_model_version"] == "v2.0"
