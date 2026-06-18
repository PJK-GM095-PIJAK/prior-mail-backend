from priormail.agents.state import PipelineState


def classify_priority(state: PipelineState, classifier) -> dict:
    """Run priority classification. Only called when is_phishing=False."""
    prediction = classifier.classify(state.subject, state.body_text)
    return {
        "priority": prediction.label,
        "priority_confidence": prediction.confidence,
        "priority_model_version": classifier.version,
    }
