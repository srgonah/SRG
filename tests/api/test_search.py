"""Tests for search endpoints."""

from fastapi.testclient import TestClient


def test_search_documents(client: TestClient, api_prefix: str, sample_search_query: dict):
    """Test search endpoint."""
    response = client.post(f"{api_prefix}/search", json=sample_search_query)

    # Should work even with empty index
    assert response.status_code == 200

    data = response.json()
    assert "query" in data
    assert "results" in data
    assert "total" in data
    assert "search_type" in data
    assert "took_ms" in data


def test_quick_search(client: TestClient, api_prefix: str):
    """Test quick search GET endpoint."""
    response = client.get(f"{api_prefix}/search/quick?q=test&top_k=5")
    assert response.status_code == 200

    data = response.json()
    assert data["query"] == "test"


def test_search_validation(client: TestClient, api_prefix: str):
    """Test search validation."""
    # Empty query
    response = client.post(f"{api_prefix}/search", json={"query": ""})
    assert response.status_code == 422

    # Invalid search type
    response = client.post(
        f"{api_prefix}/search",
        json={"query": "test", "search_type": "invalid"},
    )
    assert response.status_code == 422


def test_search_cache_stats(client: TestClient, api_prefix: str):
    """Test cache stats endpoint."""
    response = client.get(f"{api_prefix}/search/cache/stats")
    assert response.status_code == 200


def test_search_cache_invalidate(client: TestClient, api_prefix: str):
    """Test cache invalidation endpoint."""
    response = client.post(f"{api_prefix}/search/cache/invalidate")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "cache_invalidated"
