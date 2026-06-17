from __future__ import annotations

from transformers import AutoModelForSequenceClassification, AutoTokenizer


def load_phishing_classifier(settings) -> tuple[AutoModelForSequenceClassification, AutoTokenizer]:
    """Load the phishing detection model using configuration.
    The repository URI and version are read from ``settings.phishing_model_uri``.
    Returns the model and its tokenizer.
    """
    # Ensure we have a Settings instance (allow passing Settings or use global)
    if isinstance(settings, dict):
        # fallback if a dict is passed (unlikely)
        cfg = settings
    else:
        cfg = settings
    repo_id = cfg.phishing_model_repo_id
    version = cfg.phishing_model_version
    model = AutoModelForSequenceClassification.from_pretrained(
        repo_id,
        subfolder=version,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        repo_id,
        subfolder=version,
    )
    model.eval()
    return model, tokenizer
