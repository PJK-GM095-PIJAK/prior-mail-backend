"""Integration tests for the classify + health endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from fastapi import FastAPI

    from tests.conftest import StubClassifier


class TestClassifyPriority:
    async def test_happy_path_returns_envelope(
        self, client: AsyncClient, stub_classifier: StubClassifier
    ) -> None:
        resp = await client.post(
            "/api/v1/classify/priority",
            json={"subject": "Wire transfer needed", "body": "Approve before 3pm."},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["error"] is None
        assert payload["data"] == {
            "priority": "urgent",
            "priority_confidence": pytest.approx(0.91),
            "model_version": "v-test",
        }
        # The classifier received a built "{subject} [SEP] {body}" input.
        assert "[SEP]" in stub_classifier.calls[0][0]

    async def test_empty_body_and_subject_is_422(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/classify/priority", json={"subject": "", "body": ""}
        )
        assert resp.status_code == 400
        payload = resp.json()
        assert payload["data"] is None
        assert payload["error"]["code"] == "validation.invalid_field"

    async def test_503_when_model_unavailable(
        self, app_without_model: FastAPI
    ) -> None:
        transport = ASGITransport(app=app_without_model)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/classify/priority", json={"subject": "hi", "body": "there"}
            )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "service.model_unavailable"


class TestModelHealth:
    async def test_reports_version(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/health/models")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "priority_classifier" in data
        assert "phishing_detector" in data

    async def test_503_when_unavailable(self, app_without_model: FastAPI) -> None:
        transport = ASGITransport(app=app_without_model)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/health/models")
        assert resp.status_code == 200
        assert resp.json()["data"]["priority_classifier"]["status"] == "unavailable"
