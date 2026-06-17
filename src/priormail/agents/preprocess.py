from priormail.agents.state import PipelineState
from priormail.services.preprocess import clean_text


def preprocess(state: PipelineState) -> dict:
    """Normalize subject and body text for model input."""
    return {
        "body_text": clean_text(state.body_text),
        "subject": clean_text(state.subject),
        "snippet": state.body_text[:200],  # snippet from raw, before cleaning
    }
