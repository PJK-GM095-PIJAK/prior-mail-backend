"""Typed application exceptions.

Each error carries a machine-readable ``code`` (see ``API_CONTRACT.md`` §8) and
the HTTP status it maps to. Handlers in ``main.py`` render these into the
standard response envelope. Never raise bare ``Exception`` (CLAUDE.md §8).
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for all application errors.

    Args:
        code: Machine-readable error code from the API contract (§8).
        message: Human-readable message safe to return to clients.
        http_status: HTTP status this error maps to.
        details: Optional structured context (must never contain email bodies).
    """

    code: str = "internal.unknown"
    http_status: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details = details or {}


class ModelUnavailableError(AppError):
    """An ML model failed to load or is not available for inference."""

    code = "service.model_unavailable"
    http_status = 503


class ValidationError(AppError):
    """Request body or query failed a business-rule validation."""

    code = "validation.invalid_field"
    http_status = 400


class ConfigError(AppError):
    """Application configuration is invalid; the app must refuse to boot."""

    code = "internal.unknown"
    http_status = 500


class NotFoundError(AppError):
    """Requested resource does not exist."""

    code = "resource.not_found"
    http_status = 404


class ConflictError(AppError):
    """Operation conflicts with existing state (e.g. duplicate insert)."""

    code = "resource.conflict"
    http_status = 409


class EmlParseError(AppError):
    """Raised when the uploaded .eml file cannot be parsed."""
    http_status = 400
    code = "email.parse_failed"

class FileTooLargeError(AppError):
    """Raised when the uploaded file exceeds the size limit."""
    http_status = 413
    code = "email.file_too_large"
