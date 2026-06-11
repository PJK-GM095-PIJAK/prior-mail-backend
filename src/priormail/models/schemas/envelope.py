"""Standard response envelope (API_CONTRACT.md §1).

Every JSON response uses ``{ data, error, meta }``. Success: ``error`` is null.
Failure: ``data`` is null and ``error`` is populated.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorBody(BaseModel):
    """The ``error`` object in a failure envelope."""

    code: str
    message: str
    details: dict[str, Any] = {}


class Envelope(BaseModel, Generic[T]):
    """Generic success/failure envelope."""

    data: T | None = None
    error: ErrorBody | None = None
    meta: dict[str, Any] = {}


def success(data: T, *, meta: dict[str, Any] | None = None) -> Envelope[T]:
    """Build a success envelope."""
    return Envelope[T](data=data, error=None, meta=meta or {})


def failure(
    code: str, message: str, *, details: dict[str, Any] | None = None
) -> Envelope[Any]:
    """Build a failure envelope."""
    return Envelope[Any](
        data=None,
        error=ErrorBody(code=code, message=message, details=details or {}),
        meta={},
    )
