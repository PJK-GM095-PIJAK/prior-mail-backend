"""Auth-related Pydantic schemas.

Request/response models for the Google OAuth callback and user profile
endpoints. All responses are wrapped in the standard ``Envelope`` (§1).
"""

from __future__ import annotations

from pydantic import BaseModel


class GoogleCallbackRequest(BaseModel):
    """Frontend sends the Google OAuth authorization code."""

    code: str
    redirect_uri: str | None = None


class AuthTokenResponse(BaseModel):
    """Response after a successful Google OAuth token exchange."""

    gmail_connected: bool
    email: str
    display_name: str | None = None


class UserProfile(BaseModel):
    """Current user profile information."""

    id: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    gmail_connected: bool
