"""Unit tests for PriorityClassifier.predict (label mapping + confidence)."""

from __future__ import annotations

from typing import Any

import torch

from priormail.services.classifier import PriorityClassifier

ID2LABEL = {0: "urgent", 1: "high", 2: "normal", 3: "low"}


class _FakeConfig:
    id2label = ID2LABEL


class _FakeOutput:
    def __init__(self, logits: torch.Tensor) -> None:
        self.logits = logits


class _FakeModel:
    """Returns fixed logits regardless of input; records eval() calls."""

    def __init__(self, logits: torch.Tensor) -> None:
        self._logits = logits
        self.config = _FakeConfig()

    def __call__(self, **_: Any) -> _FakeOutput:
        return _FakeOutput(self._logits)

    def eval(self) -> None:  # pragma: no cover - not exercised here
        pass


class _FakeTokenizer:
    def __call__(self, inputs: list[str], **_: Any) -> dict[str, torch.Tensor]:
        return {"input_ids": torch.zeros(len(inputs), 1, dtype=torch.long)}


def _make(logits: torch.Tensor) -> PriorityClassifier:
    return PriorityClassifier(
        model=_FakeModel(logits),  # type: ignore[arg-type]
        tokenizer=_FakeTokenizer(),  # type: ignore[arg-type]
        version="v2.0",
    )


class TestPredict:
    def test_maps_argmax_to_label(self) -> None:
        # Highest logit at index 0 -> "urgent".
        clf = _make(torch.tensor([[5.0, 1.0, 0.0, -2.0]]))
        result = clf.predict(["whatever"])
        assert result[0].label == "urgent"

    def test_confidence_is_softmax_of_chosen_class(self) -> None:
        clf = _make(torch.tensor([[2.0, 1.0, 0.0, 0.0]]))
        result = clf.predict(["x"])
        expected = float(torch.tensor([2.0, 1.0, 0.0, 0.0]).softmax(-1).max())
        assert abs(result[0].confidence - expected) < 1e-6

    def test_empty_input_returns_empty(self) -> None:
        clf = _make(torch.tensor([[1.0, 0.0, 0.0, 0.0]]))
        assert clf.predict([]) == []

    def test_version_exposed(self) -> None:
        clf = _make(torch.tensor([[1.0, 0.0, 0.0, 0.0]]))
        assert clf.version == "v2.0"
