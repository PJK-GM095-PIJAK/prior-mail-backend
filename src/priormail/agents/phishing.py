from priormail.agents.state import PipelineState
from priormail.services.phishing_inference import predict_phishing


def detect_phishing(state: PipelineState, model, tokenizer, version: str) -> dict:
    """Run phishing detection. Returns early flag if phishing."""
    from priormail.services.preprocess import build_priority_input
    text = build_priority_input(state.subject, state.body_text)
    is_phishing, score = predict_phishing(model, tokenizer, text)
    return {
        "is_phishing": is_phishing,
        "phishing_score": score,
        "phishing_model_version": version,
    }
