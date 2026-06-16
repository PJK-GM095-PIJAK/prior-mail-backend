"""Tests for the sync API router."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
import uuid

from priormail.models.orm.user import User

pytestmark = pytest.mark.asyncio

@patch("priormail.api.sync_router.sync_emails")
async def test_trigger_sync_success(
    mock_sync_emails, client: AsyncClient, app, stub_classifier
):
    from priormail.core.deps import get_current_user, get_db
    
    mock_user = User(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        email="test@gmail.com",
        gmail_token_enc="encrypted_token",
        gmail_history_id="123"
    )
    
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    mock_sync_emails.return_value = {
        "synced_count": 5,
        "new_history_id": "124"
    }

    response = await client.post("/api/v1/sync")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["synced_count"] == 5
    assert data["new_history_id"] == "124"
    
    mock_sync_emails.assert_called_once()
    
    app.dependency_overrides.clear()
