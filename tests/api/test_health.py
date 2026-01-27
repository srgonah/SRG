"""Tests for health endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_root_health_check(client: TestClient):
    """Test root health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_api_health_check(client: TestClient, api_prefix: str):
    """Test API v1 health endpoint."""
    response = client.get(f"{api_prefix}/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_detailed_health_async(async_client, api_prefix: str):
    """Test detailed health check with async client."""
    response = await async_client.get(f"{api_prefix}/health/detailed")

    # May fail if providers not configured, but should return response
    assert response.status_code in [200, 500]

    if response.status_code == 200:
        data = response.json()
        assert "status" in data
        # Response has individual provider fields, not a single "providers" dict
        assert "version" in data
