"""Unit tests for the summarize agent node."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from priormail.agents.state import PipelineState
from priormail.agents.summarize import summarize


def _make_groq_client(content: str | None = "This is a summary.") -> Any:
    """Build a fake Groq client that returns the given content."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]

    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


class TestSummarize:
    def test_happy_path(self) -> None:
        client = _make_groq_client("Meeting at 10am, prepare report.")
        state = PipelineState(
            subject="Meeting", sender_email="a@b.com", body_text="Hello"
        )
        result = summarize(state, client)
        assert result["summary"] == "Meeting at 10am, prepare report."

    def test_strips_whitespace(self) -> None:
        client = _make_groq_client("  trimmed  \n")
        state = PipelineState(subject="S", sender_email="a@b.com", body_text="B")
        result = summarize(state, client)
        assert result["summary"] == "trimmed"

    def test_none_content_returns_none(self) -> None:
        client = _make_groq_client(None)
        state = PipelineState(subject="S", sender_email="a@b.com", body_text="B")
        result = summarize(state, client)
        assert result["summary"] is None

    def test_api_error_returns_none(self) -> None:
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("Rate limited")
        state = PipelineState(subject="S", sender_email="a@b.com", body_text="B")
        result = summarize(state, client)
        assert result["summary"] is None

    def test_body_capped_at_3000(self) -> None:
        client = _make_groq_client("summary")
        long_body = "x" * 5000
        state = PipelineState(
            subject="S", sender_email="a@b.com", body_text=long_body
        )
        summarize(state, client)
        # Verify the prompt was called with truncated body
        call_args = client.chat.completions.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        # Body in prompt should be at most 3000 chars of the original
        assert "x" * 3001 not in prompt
