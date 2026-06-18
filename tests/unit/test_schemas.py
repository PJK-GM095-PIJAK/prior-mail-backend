"""Unit tests for Pydantic schemas."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from priormail.models.schemas.analysis import AnalysisResult, ExtractedTask
from priormail.models.schemas.envelope import Envelope, failure, success


class TestExtractedTask:
    def test_with_due_date(self) -> None:
        task = ExtractedTask(description="Submit report", due_date="2026-06-30")
        assert task.description == "Submit report"
        assert task.due_date is not None

    def test_without_due_date(self) -> None:
        task = ExtractedTask(description="Review code")
        assert task.due_date is None

    def test_empty_description_allowed(self) -> None:
        task = ExtractedTask(description="")
        assert task.description == ""


class TestAnalysisResult:
    def test_minimal_valid(self) -> None:
        result = AnalysisResult(
            subject="Test",
            sender_email="a@b.com",
            snippet="Hello",
            body_text="Hello world",
            is_phishing=False,
            phishing_score=0.1,
            processed_at=datetime.now(UTC),
        )
        assert result.priority is None  # default None
        assert result.tasks == []  # default empty

    def test_phishing_score_must_be_0_to_1(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisResult(
                subject="X",
                sender_email="a@b.com",
                snippet="S",
                body_text="B",
                is_phishing=True,
                phishing_score=1.5,  # invalid
                processed_at=datetime.now(UTC),
            )

    def test_priority_confidence_must_be_0_to_1(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisResult(
                subject="X",
                sender_email="a@b.com",
                snippet="S",
                body_text="B",
                is_phishing=False,
                phishing_score=0.1,
                priority_confidence=-0.1,  # invalid
                processed_at=datetime.now(UTC),
            )


class TestEnvelope:
    def test_success_envelope(self) -> None:
        env = success({"key": "value"})
        assert env.data == {"key": "value"}
        assert env.error is None

    def test_failure_envelope(self) -> None:
        env = failure("test.error", "Something went wrong")
        assert env.data is None
        assert env.error is not None
        assert env.error.code == "test.error"
        assert env.error.message == "Something went wrong"

    def test_success_with_meta(self) -> None:
        env = success("data", meta={"page": 1})
        assert env.meta == {"page": 1}
