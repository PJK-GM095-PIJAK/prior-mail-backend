from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ExtractedTask(BaseModel):
    description: str
    due_date: date | None = None

class AnalysisResult(BaseModel):
    subject: str
    sender_email: str
    sender_name: str | None = None
    received_at: datetime | None = None
    snippet: str                              # first 200 chars of body
    body_text: str
    is_phishing: bool
    phishing_score: float = Field(ge=0, le=1)
    priority: str | None = None          # None when is_phishing=True
    priority_confidence: float = Field(default=0.0, ge=0, le=1)
    summary: str | None = None
    tasks: list[ExtractedTask] = []
    processed_at: datetime
    model_versions: dict[str, str] = {}
