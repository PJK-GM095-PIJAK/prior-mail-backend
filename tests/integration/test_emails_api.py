"""Tests for the emails API router."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock
import uuid
from datetime import datetime, timezone

from priormail.models.orm.user import User
from priormail.models.orm.email import Email

pytestmark = pytest.mark.asyncio

async def test_list_emails(client: AsyncClient, app, stub_classifier):
    from priormail.core.deps import get_current_user, get_db
    
    user_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    mock_user = User(
        id=user_id,
        email="test@gmail.com",
    )
    
    email_id = uuid.uuid4()
    mock_email = Email(
        id=email_id,
        user_id=user_id,
        gmail_id="msg123",
        subject="Test subject",
        sender="sender@example.com",
        received_at=datetime.now(timezone.utc),
        is_read=False,
        labels=["INBOX"]
    )
    
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [mock_email]
    mock_session.execute.return_value = mock_result
    
    app.dependency_overrides[get_db] = lambda: mock_session

    response = await client.get("/api/v1/emails?limit=10")

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["gmail_id"] == "msg123"
    assert data[0]["subject"] == "Test subject"
    
    app.dependency_overrides.clear()

async def test_get_email_detail(client: AsyncClient, app, stub_classifier):
    from priormail.core.deps import get_current_user, get_db
    
    user_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    mock_user = User(id=user_id, email="test@gmail.com")
    
    email_id = uuid.uuid4()
    mock_email = Email(
        id=email_id,
        user_id=user_id,
        gmail_id="msg123",
        subject="Test Detail",
        sender="sender@example.com",
        received_at=datetime.now(timezone.utc),
        is_read=True,
        raw_body="This is a body",
        labels=["INBOX"]
    )
    
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_email
    mock_session.execute.return_value = mock_result
    
    app.dependency_overrides[get_db] = lambda: mock_session

    response = await client.get(f"/api/v1/emails/{email_id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["subject"] == "Test Detail"
    assert data["raw_body"] == "This is a body"
    
    # Verify audit log was created
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
    
    app.dependency_overrides.clear()
