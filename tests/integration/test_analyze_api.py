"""Integration tests for POST /api/v1/emails/analyze and health endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from fastapi import FastAPI


class TestAnalyzeEndpoint:
    """Tests for the full .eml upload → pipeline → response flow."""

    async def test_happy_path_returns_analysis_result(
        self, pipeline_client: AsyncClient, sample_eml_bytes: bytes
    ) -> None:
        resp = await pipeline_client.post(
            "/api/v1/emails/analyze",
            files={"file": ("test.eml", sample_eml_bytes, "message/rfc822")},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["error"] is None
        data = payload["data"]
        assert data["subject"] == "Meeting Tomorrow at 10am"
        assert data["sender_email"] == "john@example.com"
        assert data["is_phishing"] is False
        assert data["priority"] is not None
        assert data["summary"] is not None
        assert "processed_at" in data
        assert "model_versions" in data

    async def test_returns_tasks_list(
        self, pipeline_client: AsyncClient, sample_eml_bytes: bytes
    ) -> None:
        resp = await pipeline_client.post(
            "/api/v1/emails/analyze",
            files={"file": ("test.eml", sample_eml_bytes, "message/rfc822")},
        )
        data = resp.json()["data"]
        assert isinstance(data["tasks"], list)

    async def test_file_too_large_returns_413(
        self, pipeline_client: AsyncClient
    ) -> None:
        # 6 MB file — exceeds the 5 MB limit.
        big_content = b"X" * (6 * 1024 * 1024)
        resp = await pipeline_client.post(
            "/api/v1/emails/analyze",
            files={"file": ("huge.eml", big_content, "message/rfc822")},
        )
        assert resp.status_code == 413
        assert resp.json()["error"]["code"] == "email.file_too_large"

    async def test_pipeline_not_initialized_returns_503(
        self, app_without_model: FastAPI
    ) -> None:
        transport = ASGITransport(app=app_without_model)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/emails/analyze",
                files={"file": ("test.eml", b"From: a@b.com\nSubject: Hi\n\nBody", "message/rfc822")},
            )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "service.model_unavailable"

    async def test_no_file_returns_422(
        self, pipeline_client: AsyncClient
    ) -> None:
        resp = await pipeline_client.post("/api/v1/emails/analyze")
        assert resp.status_code == 400 or resp.status_code == 422


class TestModelHealth:
    async def test_reports_loaded_models(
        self, pipeline_client: AsyncClient
    ) -> None:
        resp = await pipeline_client.get("/api/v1/health/models")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["priority_classifier"]["status"] == "loaded"
        assert data["phishing_detector"]["status"] == "loaded"

    async def test_reports_unavailable_when_no_models(
        self, app_without_model: FastAPI
    ) -> None:
        transport = ASGITransport(app=app_without_model)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/health/models")
        assert resp.status_code == 200
        assert resp.json()["data"]["priority_classifier"]["status"] == "unavailable"
