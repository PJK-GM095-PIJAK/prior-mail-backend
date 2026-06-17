import json

from groq import Groq

from priormail.agents.state import PipelineState

TASK_PROMPT = """\
Extract any actionable tasks or deadlines from the email below.
Return a JSON array. Each item must have "description" (string) and "due_date" (YYYY-MM-DD or null).
If there are no tasks, return an empty array [].
Return ONLY the JSON array, no explanation.

Subject: {subject}
From: {sender}

{body}"""

def extract_tasks(state: PipelineState, llm_client: Groq) -> dict:
    """Call Groq to extract tasks as a JSON array."""
    from priormail.core.config import get_settings
    settings = get_settings()

    prompt = TASK_PROMPT.format(
        subject=state.subject,
        sender=state.sender_email,
        body=state.body_text[:3000],
    )
    response = llm_client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.1,  # low temp for structured output
    )
    raw = response.choices[0].message.content.strip()

    # Parse JSON — one retry with a format reminder if it fails.
    try:
        tasks = json.loads(raw)
        if not isinstance(tasks, list):
            tasks = []
    except json.JSONDecodeError:
        tasks = []

    return {"tasks": tasks}
