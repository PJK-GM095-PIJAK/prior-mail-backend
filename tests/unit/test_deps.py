"""Tests for auth dependencies in deps.py."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from priormail.core.config import Settings, get_settings
from priormail.core.deps import get_current_user, get_current_user_id
from priormail.core.errors import AuthenticationError
from priormail.models.orm.user import User

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_settings() -> Settings:
    settings = get_settings()
    settings.supabase_jwt_secret = "test-secret"
    return settings

async def test_get_current_user_id_missing_credentials():
    with pytest.raises(AuthenticationError, match="Missing Authorization header"):
        await get_current_user_id(None)

@patch("jose.jwt.decode")
async def test_get_current_user_id_valid(mock_decode, mock_settings):
    mock_decode.return_value = {"sub": "12345678-1234-5678-1234-567812345678"}
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid_token")
    
    sub = await get_current_user_id(creds)
    assert sub == "12345678-1234-5678-1234-567812345678"
    mock_decode.assert_called_once_with(
        "valid_token", 
        "test-secret", 
        algorithms=["HS256"], 
        audience="authenticated"
    )

@patch("jose.jwt.decode")
async def test_get_current_user_id_invalid(mock_decode, mock_settings):
    from jose import JWTError
    mock_decode.side_effect = JWTError("Expired token")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid_token")
    
    with pytest.raises(AuthenticationError, match="Invalid or expired token"):
        await get_current_user_id(creds)

async def test_get_current_user_new(mock_settings):
    """Test getting current user when user does not exist in DB yet (upsert)."""
    uid_str = "12345678-1234-5678-1234-567812345678"
    uid = uuid.UUID(uid_str)
    
    # Mock session
    session = AsyncMock()
    
    from unittest.mock import MagicMock
    
    # Mock the execute result for user lookup to return None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    
    user = await get_current_user(user_id=uid_str, session=session)
    
    assert user.id == uid
    assert user.email == f"{uid_str}@pending"
    session.add.assert_called_once()
    session.flush.assert_called_once()

async def test_get_current_user_existing(mock_settings):
    """Test getting current user when user already exists."""
    uid_str = "12345678-1234-5678-1234-567812345678"
    uid = uuid.UUID(uid_str)
    existing_user = User(id=uid, email="test@example.com")
    
    from unittest.mock import MagicMock
    
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user
    session.execute.return_value = mock_result
    
    user = await get_current_user(user_id=uid_str, session=session)
    
    assert user is existing_user
    session.add.assert_not_called()
