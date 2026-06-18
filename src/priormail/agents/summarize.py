"""LLM summarization node — calls Groq to generate a short email summary."""

from __future__ import annotations

from groq import Groq

from priormail.agents.state import PipelineState
from priormail.core.logging import get_logger

logger = get_logger(__name__)

SUMMARIZE_PROMPT = """\
Summarize the following email in 2-3 sentences. Be concise and focus on the key point and any required action.

Subject: {subject}
From: {sender}

{body}

Summary:"""


def summarize(state: PipelineState, llm_client: Groq) -> dict:
    """Call Groq to generate a short email summary.

    Returns a partial state dict with the ``summary`` key.
    On failure (network, rate-limit, bad response) the summary is set to
    ``None`` and the error is logged — the pipeline continues rather than
    crashing, because a missing summary is non-fatal.
    """
    from priormail.core.config import get_settings

    settings = get_settings()

    prompt = SUMMARIZE_PROMPT.format(
        subject=state.subject,
        sender=state.sender_email,
        body=state.body_text[:3000],  # cap to stay within TPM budget
    )
    try:
        response = llm_client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
        )
        content = response.choices[0].message.content
        summary = content.strip() if content else None
    except Exception:
        logger.exception("summarize_llm_failed")
        summary = None

    return {"summary": summary}
