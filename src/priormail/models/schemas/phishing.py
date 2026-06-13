from __future__ import annotations

from pydantic import BaseModel, Field

class PhishingData(BaseModel):
    """Payload of a successful phishing detection response."""

    is_phishing: bool = Field(description="True if the email is classified as phishing.")
    phishing_score: float = Field(
        description="Confidence (probability) that the email is phishing, 0‑1."
    )
