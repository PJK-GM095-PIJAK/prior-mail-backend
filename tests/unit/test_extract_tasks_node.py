"""Unit tests for the extract_tasks agent node."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from priormail.agents.extract_tasks import extract_tasks
from priormail.agents.state import PipelineState


def _make_groq_client(content: str | None = "[]") -> Any:
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


class TestExtractTasks:
    def test_happy_path_with_tasks(self) -> None:
        json_str = '[{"description": "Submit report", "due_date": "2026-06-30"}]'
        client = _make_groq_client(json_str)
        state = PipelineState(subject="S", sender_email="a@b.com", body_text="B")
        result = extract_tasks(state, client)
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["description"] == "Submit report"
        assert result["tasks"][0]["due_date"] == "2026-06-30"

    def test_empty_array(self) -> None:
        client = _make_groq_client("[]")
        state = PipelineState(subject="S", sender_email="a@b.com", body_text="B")
        result = extract_tasks(state, client)
        assert result["tasks"] == []

    def test_invalid_json_returns_empty_list(self) -> None:
        client = _make_groq_client("This is not valid JSON at all")
        state = PipelineState(subject="S", sender_email="a@b.com", body_text="B")
        result = extract_tasks(state, client)
        assert result["tasks"] == []

    def test_non_list_json_returns_empty_list(self) -> None:
        client = _make_groq_client('{"not": "a list"}')
        state = PipelineState(subject="S", sender_email="a@b.com", body_text="B")
        result = extract_tasks(state, client)
        assert result["tasks"] == []

    def test_api_error_returns_empty_list(self) -> None:
        client = MagicMock()
        client.chat.completions.create.side_effect = ConnectionError("timeout")
        state = PipelineState(subject="S", sender_email="a@b.com", body_text="B")
        result = extract_tasks(state, client)
        assert result["tasks"] == []

    def test_none_content_returns_empty_list(self) -> None:
        client = _make_groq_client(None)
        state = PipelineState(subject="S", sender_email="a@b.com", body_text="B")
        result = extract_tasks(state, client)
        assert result["tasks"] == []

    def test_multiple_tasks(self) -> None:
        json_str = (
            '['
            '{"description": "Task 1", "due_date": null},'
            '{"description": "Task 2", "due_date": "2026-07-01"}'
            ']'
        )
        client = _make_groq_client(json_str)
        state = PipelineState(subject="S", sender_email="a@b.com", body_text="B")
        result = extract_tasks(state, client)
        assert len(result["tasks"]) == 2
