"""Tests for the auth API router."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

from priormail.models.orm.user import User

pytestmark = pytest.mark.asyncio

@patch("priormail.api.auth.exchange_code_for_tokens")
@patch("priormail.api.auth.get_user_profile")
async def test_google_callback_success(
    mock_get_profile, mock_exchange, client: AsyncClient, app, stub_classifier
):
    # Mocking the dependency in app
    from priormail.core.deps import get_current_user_id
    app.dependency_overrides[get_current_user_id] = lambda: "12345678-1234-5678-1234-567812345678"
    
    # Mock the DB session
    from priormail.core.deps import get_db
    
    from unittest.mock import MagicMock
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    
    app.dependency_overrides[get_db] = lambda: mock_session

    mock_exchange.return_value = {
        "access_token": "mock-access",
        "refresh_token": "mock-refresh"
    }
    mock_get_profile.return_value = {
        "emailAddress": "test@gmail.com",
        "historyId": "9999"
    }

    response = await client.post(
        "/api/v1/auth/google/callback",
        json={"code": "mock-auth-code", "redirect_uri": "http://localhost:3000/callback"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["gmail_connected"] is True
    assert data["email"] == "test@gmail.com"
    
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
    
    app.dependency_overrides.clear()

async def test_get_me(client: AsyncClient, app, stub_classifier):
    from priormail.core.deps import get_current_user
    import uuid
    
    mock_user = User(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        email="test@gmail.com",
        display_name="Test User",
        gmail_token_enc="encrypted_token"
    )
    
    app.dependency_overrides[get_current_user] = lambda: mock_user

    response = await client.get("/api/v1/auth/me")
    
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["email"] == "test@gmail.com"
    assert data["display_name"] == "Test User"
    assert data["gmail_connected"] is True
    assert data["id"] == "12345678-1234-5678-1234-567812345678"
    
    app.dependency_overrides.clear()
