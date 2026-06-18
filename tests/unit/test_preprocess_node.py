"""Unit tests for the preprocess agent node."""

from __future__ import annotations

from priormail.agents.preprocess import preprocess
from priormail.agents.state import PipelineState


class TestPreprocessNode:
    def test_cleans_html_from_body(self) -> None:
        state = PipelineState(
            body_text="<p>Hello <b>world</b></p>",
            subject="Test Subject",
        )
        result = preprocess(state)
        assert "<p>" not in result["body_text"]
        assert "<b>" not in result["body_text"]
        assert "Hello" in result["body_text"]

    def test_cleans_subject(self) -> None:
        state = PipelineState(
            body_text="plain body",
            subject="Check https://evil.com now",
        )
        result = preprocess(state)
        assert "[URL]" in result["subject"]

    def test_snippet_from_raw_body(self) -> None:
        raw_body = "A" * 300
        state = PipelineState(body_text=raw_body, subject="S")
        result = preprocess(state)
        assert result["snippet"] == raw_body[:200]

    def test_masks_email_addresses(self) -> None:
        state = PipelineState(
            body_text="Contact me at user@domain.com for details.",
            subject="Info",
        )
        result = preprocess(state)
        assert "[EMAIL]" in result["body_text"]
        assert "user@domain.com" not in result["body_text"]

    def test_collapses_whitespace(self) -> None:
        state = PipelineState(
            body_text="Hello   \n\n  world   \t  !",
            subject="Test",
        )
        result = preprocess(state)
        assert "  " not in result["body_text"]

    def test_empty_body(self) -> None:
        state = PipelineState(body_text="", subject="")
        result = preprocess(state)
        assert result["body_text"] == ""
        assert result["snippet"] == ""
