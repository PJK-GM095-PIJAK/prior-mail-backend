"""Unit tests for the phishing detection agent node."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import torch

from priormail.agents.phishing import detect_phishing
from priormail.agents.state import PipelineState


def _make_model(phishing_prob: float) -> Any:
    """Create a fake model that returns the given phishing probability."""
    not_phishing_logit = 1.0 - phishing_prob
    phishing_logit = phishing_prob

    model = MagicMock()
    result = MagicMock()
    # We need softmax of [not_phishing, phishing] to approximate the desired prob.
    # Use logits that roughly produce the desired softmax output.
    import math

    logit_0 = math.log(max(not_phishing_logit, 1e-6))
    logit_1 = math.log(max(phishing_logit, 1e-6))
    result.logits = torch.tensor([[logit_0, logit_1]])
    model.return_value = result
    return model


def _make_tokenizer() -> Any:
    tokenizer = MagicMock()
    tokenizer.return_value = {"input_ids": torch.zeros(1, 5, dtype=torch.long)}
    return tokenizer


class TestDetectPhishing:
    def test_not_phishing(self) -> None:
        model = _make_model(0.1)
        tokenizer = _make_tokenizer()
        state = PipelineState(subject="Hello", body_text="Normal email body")
        result = detect_phishing(state, model, tokenizer, "v-test")
        assert result["is_phishing"] is False
        assert 0.0 <= result["phishing_score"] <= 1.0
        assert result["phishing_model_version"] == "v-test"

    def test_phishing_detected(self) -> None:
        model = _make_model(0.95)
        tokenizer = _make_tokenizer()
        state = PipelineState(
            subject="URGENT: Verify your account",
            body_text="Click here to confirm your password",
        )
        result = detect_phishing(state, model, tokenizer, "v-test")
        assert result["is_phishing"] is True
        assert result["phishing_score"] >= 0.5

    def test_version_passed_through(self) -> None:
        model = _make_model(0.1)
        tokenizer = _make_tokenizer()
        state = PipelineState(subject="Test", body_text="Body")
        result = detect_phishing(state, model, tokenizer, "v2.0-phishing")
        assert result["phishing_model_version"] == "v2.0-phishing"
