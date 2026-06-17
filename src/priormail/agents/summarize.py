from groq import Groq

from priormail.agents.state import PipelineState

SUMMARIZE_PROMPT = """\
Summarize the following email in 2-3 sentences. Be concise and focus on the key point and any required action.

Subject: {subject}
From: {sender}

{body}

Summary:"""

def summarize(state: PipelineState, llm_client: Groq) -> dict:
    """Call Groq to generate a short email summary."""
    from priormail.core.config import get_settings
    settings = get_settings()

    prompt = SUMMARIZE_PROMPT.format(
        subject=state.subject,
        sender=state.sender_email,
        body=state.body_text[:3000],  # cap to stay within TPM budget
    )
    response = llm_client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.3,
    )
    summary = response.choices[0].message.content.strip()
    return {"summary": summary}
