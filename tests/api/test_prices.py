"""API smoke tests for price history endpoints."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_price_store
from src.api.main import app


@pytest.fixture
def mock_price_store():
    """Create mock price history store."""
    store = AsyncMock()
    store.get_price_history.return_value = [
        {
            "item_name": "steel pipe 4 inch",
            "hs_code": "7304.19",
            "seller_name": "ACME Steel",
            "invoice_date": "2024-06-15",
            "quantity": 100,
            "unit_price": 12.50,
            "currency": "USD",
        },
    ]
    store.get_price_stats.return_value = [
        {
            "item_name": "steel pipe 4 inch",
            "hs_code": "7304.19",
            "seller_name": "ACME Steel",
            "currency": "USD",
            "occurrence_count": 5,
            "min_price": 10.00,
            "max_price": 15.00,
            "avg_price": 12.50,
            "price_trend": "stable",
            "first_seen": "2024-01-10",
            "last_seen": "2024-06-15",
        },
    ]
    return store


@pytest.fixture
async def price_client(mock_price_store):
    """Async client with price store dependency overridden."""
    app.dependency_overrides[get_price_store] = lambda: mock_price_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_price_store, None)


class TestPriceHistoryAPI:
    """Smoke tests for price history API."""

    async def test_history_endpoint_exists(self, price_client: AsyncClient):
        """Test that GET /api/prices/history endpoint exists."""
        response = await price_client.get("/api/prices/history")
        assert response.status_code != 404

    async def test_history_returns_entries(self, price_client: AsyncClient):
        """Test that GET /api/prices/history returns entries."""
        response = await price_client.get("/api/prices/history")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data
        assert data["total"] == 1
        assert data["entries"][0]["item_name"] == "steel pipe 4 inch"

    async def test_history_with_item_filter(self, price_client: AsyncClient):
        """Test that GET /api/prices/history accepts item filter."""
        response = await price_client.get(
            "/api/prices/history", params={"item": "steel"}
        )
        assert response.status_code == 200

    async def test_history_with_seller_filter(self, price_client: AsyncClient):
        """Test that GET /api/prices/history accepts seller filter."""
        response = await price_client.get(
            "/api/prices/history", params={"seller": "ACME"}
        )
        assert response.status_code == 200

    async def test_history_with_date_range(self, price_client: AsyncClient):
        """Test that GET /api/prices/history accepts date filters."""
        response = await price_client.get(
            "/api/prices/history",
            params={"date_from": "2024-01-01", "date_to": "2024-12-31"},
        )
        assert response.status_code == 200

    async def test_stats_endpoint_exists(self, price_client: AsyncClient):
        """Test that GET /api/prices/stats endpoint exists."""
        response = await price_client.get("/api/prices/stats")
        assert response.status_code != 404

    async def test_stats_returns_data(self, price_client: AsyncClient):
        """Test that GET /api/prices/stats returns stats list."""
        response = await price_client.get("/api/prices/stats")
        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        assert "total" in data
        assert data["total"] == 1
        assert data["stats"][0]["item_name"] == "steel pipe 4 inch"

    async def test_stats_with_item_filter(self, price_client: AsyncClient):
        """Test that GET /api/prices/stats accepts item filter."""
        response = await price_client.get(
            "/api/prices/stats", params={"item": "steel"}
        )
        assert response.status_code == 200
