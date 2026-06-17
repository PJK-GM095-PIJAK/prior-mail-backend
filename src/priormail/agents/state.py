from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PipelineState(BaseModel):
    # --- Input (set by parse_eml node) ---
    raw_eml: bytes = b""
    subject: str = ""
    sender_email: str = ""
    sender_name: str | None = None
    received_at: datetime | None = None
    body_text: str = ""
    snippet: str = ""

    # --- Phishing node output ---
    is_phishing: bool = False
    phishing_score: float = 0.0
    phishing_model_version: str = ""

    # --- Priority node output (skipped if is_phishing=True) ---
    priority: str | None = None
    priority_confidence: float = 0.0
    priority_model_version: str = ""

    # --- LLM node outputs ---
    summary: str | None = None
    tasks: list[dict] = Field(default_factory=list)  # {description, due_date}

    # --- Meta ---
    processed_at: datetime | None = None
    error: str | None = None
