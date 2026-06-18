"""LLM task extraction node — calls Groq to extract actionable tasks from an email."""

from __future__ import annotations

import json

from groq import Groq

from priormail.agents.state import PipelineState
from priormail.core.logging import get_logger

logger = get_logger(__name__)

TASK_PROMPT = """\
Extract any actionable tasks or deadlines from the email below.
Return a JSON array. Each item must have "description" (string) and "due_date" (YYYY-MM-DD or null).
If there are no tasks, return an empty array [].
Return ONLY the JSON array, no explanation.

Subject: {subject}
From: {sender}

{body}"""


def extract_tasks(state: PipelineState, llm_client: Groq) -> dict:
    """Call Groq to extract tasks as a JSON array.

    Returns a partial state dict with the ``tasks`` key (list of dicts).
    On failure (network, rate-limit, unparseable JSON) tasks defaults to
    an empty list and the error is logged — a missing task list is non-fatal.
    """
    from priormail.core.config import get_settings

    settings = get_settings()

    prompt = TASK_PROMPT.format(
        subject=state.subject,
        sender=state.sender_email,
        body=state.body_text[:3000],
    )

    try:
        response = llm_client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.1,  # low temp for structured output
        )
        content = response.choices[0].message.content
        raw = content.strip() if content else "[]"
    except Exception:
        logger.exception("extract_tasks_llm_failed")
        return {"tasks": []}

    # Parse JSON — graceful fallback to empty list on bad output.
    try:
        tasks = json.loads(raw)
        if not isinstance(tasks, list):
            logger.warning("extract_tasks_unexpected_type", raw_type=type(tasks).__name__)
            tasks = []
    except json.JSONDecodeError:
        logger.warning("extract_tasks_json_parse_failed", raw_preview=raw[:200])
        tasks = []

    return {"tasks": tasks}
