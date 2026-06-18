from __future__ import annotations

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def predict_phishing(
    model: AutoModelForSequenceClassification,
    tokenizer: AutoTokenizer,
    text: str,
) -> tuple[bool, float]:
    """Return (is_phishing, confidence_score) for *text*.
    Assumes the model's second class (index 1) corresponds to *phishing*.
    """
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )
    with torch.no_grad():
        logits = model(**inputs).logits
    probs = logits.softmax(dim=-1).squeeze()
    phishing_prob = float(probs[1])  # index 1 = phishing
    return phishing_prob >= 0.5, phishing_prob
