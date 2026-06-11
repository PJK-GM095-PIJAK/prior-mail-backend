"""Pydantic schemas for the priority classify endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClassifyRequest(BaseModel):
    """Request body for ``POST /api/v1/classify/priority``."""

    subject: str = Field(default="", description="Email subject line.")
    body: str = Field(default="", description="Email body (plain text or HTML).")

    @model_validator(mode="after")
    def _at_least_one_field(self) -> ClassifyRequest:
        if not self.subject.strip() and not self.body.strip():
            raise ValueError("at least one of 'subject' or 'body' must be non-empty")
        return self


class ClassifyData(BaseModel):
    """Payload of a successful classification response."""

    # 'model_version' would otherwise clash with Pydantic's protected 'model_' namespace.
    model_config = ConfigDict(protected_namespaces=())

    priority: str = Field(description="One of: urgent, high, normal, low.")
    priority_confidence: float = Field(
        description="Softmax probability of the chosen class (0–1)."
    )
    model_version: str = Field(description="Version of the model that produced this.")
