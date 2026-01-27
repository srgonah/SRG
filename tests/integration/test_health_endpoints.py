"""
Integration tests for health check endpoints.

Tests the /health and /api/health/* endpoints with actual FastAPI app.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create sync test client."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_basic_health_check(self, client):
        """Test basic health check returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_check_includes_version(self, client):
        """Test health check includes version string."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"

    def test_api_health_has_uptime(self, client):
        """Test API health endpoint has uptime_seconds."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_llm_health_endpoint_exists(self, client):
        """Test /api/health/llm endpoint exists and returns expected structure."""
        response = client.get("/api/health/llm")

        # May be degraded if no LLM configured, but should return valid response
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "llm" in data
        if data["llm"]:
            assert "name" in data["llm"]
            assert "available" in data["llm"]

    def test_db_health_endpoint_exists(self, client):
        """Test /api/health/db endpoint exists and returns expected structure."""
        response = client.get("/api/health/db")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "database" in data
        if data["database"]:
            assert "name" in data["database"]
            assert "available" in data["database"]

    def test_search_health_endpoint_exists(self, client):
        """Test /api/health/search endpoint exists and returns expected structure."""
        response = client.get("/api/health/search")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "vector_store" in data
        if data["vector_store"]:
            assert "name" in data["vector_store"]
            assert "available" in data["vector_store"]

    def test_full_health_check(self, client):
        """Test full health check returns all components."""
        response = client.get("/api/health/full")

        assert response.status_code == 200
        data = response.json()

        # Should have status
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

        # Should include all providers (may be None if not configured)
        assert "llm" in data
        assert "embedding" in data
        assert "database" in data
        assert "vector_store" in data

    def test_api_health_response_schema(self, client):
        """Test API health response matches expected schema."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["uptime_seconds"], (int, float))

        # Optional provider fields should be None or valid object
        for provider_key in ["llm", "embedding", "database", "vector_store"]:
            if data.get(provider_key) is not None:
                provider = data[provider_key]
                assert isinstance(provider["name"], str)
                assert isinstance(provider["available"], bool)


class TestHealthEndpointErrors:
    """Tests for health endpoint error handling."""

    def test_invalid_health_path_returns_404(self, client):
        """Test invalid health subpath returns 404."""
        response = client.get("/api/health/invalid")

        assert response.status_code == 404

    def test_health_method_not_allowed(self, client):
        """Test POST to health endpoint returns 405."""
        response = client.post("/health")

        assert response.status_code == 405
