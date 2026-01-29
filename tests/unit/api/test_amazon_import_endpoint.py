"""
API tests for Amazon import endpoint.

Tests the /api/materials/import/amazon endpoints with mocked SearchAPI.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class MockSearchResult:
    """Mock Amazon search result for testing."""

    def __init__(self, asin: str, title: str, brand: str | None = None):
        self.asin = asin
        self.title = title
        self.brand = brand
        self.price = "AED 99.00"
        self.price_value = 99.0
        self.currency = "AED"
        self.product_url = f"https://www.amazon.ae/dp/{asin}"
        self.rating = 4.5
        self.reviews_count = 100
        self.image_url = None
        self.is_prime = False


class TestAmazonImportEndpoint:
    """Tests for Amazon import API endpoints."""

    def test_get_categories(self, client):
        """Test GET /api/materials/import/amazon/categories returns categories."""
        response = client.get("/api/materials/import/amazon/categories")

        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert isinstance(data["categories"], dict)
        assert len(data["categories"]) > 0

        # Check expected categories exist
        assert "Electronics" in data["categories"]
        assert "Home & Kitchen" in data["categories"]

    @patch("src.api.routes.amazon_import.AmazonSearchAPIClient")
    @patch("src.api.routes.amazon_import.AmazonImportService")
    def test_import_amazon_success(self, mock_service_class, mock_client_class, client):
        """Test POST /api/materials/import/amazon with successful import."""
        # Setup mock search client
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value=[
                MockSearchResult("B09TEST001", "Test Product 1", "BrandA"),
                MockSearchResult("B09TEST002", "Test Product 2", "BrandB"),
            ]
        )
        mock_client_class.return_value = mock_client

        # Setup mock import service
        mock_service = AsyncMock()
        mock_service.import_items = AsyncMock(
            return_value=AsyncMock(
                items_found=2,
                items_saved=2,
                items_skipped=0,
                items_error=0,
                items=[
                    AsyncMock(
                        asin="B09TEST001",
                        title="Test Product 1",
                        brand="BrandA",
                        price="AED 99.00",
                        price_value=99.0,
                        currency="AED",
                        product_url="https://www.amazon.ae/dp/B09TEST001",
                        status="saved",
                        material_id="mat-001",
                        error_message=None,
                        existing_material_id=None,
                    ),
                    AsyncMock(
                        asin="B09TEST002",
                        title="Test Product 2",
                        brand="BrandB",
                        price="AED 99.00",
                        price_value=99.0,
                        currency="AED",
                        product_url="https://www.amazon.ae/dp/B09TEST002",
                        status="saved",
                        material_id="mat-002",
                        error_message=None,
                        existing_material_id=None,
                    ),
                ],
            )
        )
        mock_service_class.return_value = mock_service

        # Make request
        response = client.post(
            "/api/materials/import/amazon",
            json={
                "category": "Electronics",
                "subcategory": "all",
                "limit": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_found"] == 2
        assert data["items_saved"] == 2
        assert data["items_skipped"] == 0
        assert len(data["items"]) == 2

    @patch("src.api.routes.amazon_import.AmazonSearchAPIClient")
    def test_import_amazon_no_results(self, mock_client_class, client):
        """Test POST /api/materials/import/amazon with no search results."""
        # Setup mock to return empty results
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=[])
        mock_client_class.return_value = mock_client

        response = client.post(
            "/api/materials/import/amazon",
            json={
                "category": "Electronics",
                "limit": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_found"] == 0
        assert data["items_saved"] == 0
        assert len(data["items"]) == 0

    def test_import_amazon_missing_category(self, client):
        """Test POST /api/materials/import/amazon without required category."""
        response = client.post(
            "/api/materials/import/amazon",
            json={
                "limit": 10,
            },
        )

        assert response.status_code == 422  # Validation error

    def test_import_amazon_invalid_limit(self, client):
        """Test POST /api/materials/import/amazon with invalid limit."""
        response = client.post(
            "/api/materials/import/amazon",
            json={
                "category": "Electronics",
                "limit": 100,  # Max is 50
            },
        )

        assert response.status_code == 422  # Validation error

    @patch("src.api.routes.amazon_import.AmazonSearchAPIClient")
    def test_preview_amazon_success(self, mock_client_class, client):
        """Test POST /api/materials/import/amazon/preview returns preview."""
        # Setup mock search client
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value=[
                MockSearchResult("B09TEST001", "New Product", "Brand"),
            ]
        )
        mock_client_class.return_value = mock_client

        # Mock the store's find methods to return None (no duplicates)
        with patch("src.api.routes.amazon_import.get_mat_store") as mock_get_store:
            mock_store = AsyncMock()
            mock_store.find_by_normalized_name = AsyncMock(return_value=None)
            mock_store.find_by_synonym = AsyncMock(return_value=None)
            mock_get_store.return_value = mock_store

            response = client.post(
                "/api/materials/import/amazon/preview",
                json={
                    "category": "Electronics",
                    "limit": 5,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["items_found"] == 1
        assert data["items_saved"] == 0  # Preview mode - nothing saved
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "pending"


class TestAmazonSearchAPIClient:
    """Tests for the SearchAPI client."""

    @pytest.mark.asyncio
    async def test_search_builds_correct_params(self):
        """Test that search builds correct API parameters."""
        from src.infrastructure.scrapers.amazon_search_api import AmazonSearchAPIClient

        # Test without API key - should return empty
        client = AmazonSearchAPIClient(api_key="")
        results = await client.search("test query")
        assert results == []

    def test_get_amazon_categories(self):
        """Test get_amazon_categories returns expected structure."""
        from src.infrastructure.scrapers.amazon_search_api import get_amazon_categories

        categories = get_amazon_categories()
        assert isinstance(categories, dict)
        assert "Electronics" in categories
        assert "all" in categories["Electronics"]

    def test_get_category_code(self):
        """Test get_category_code returns correct codes."""
        from src.infrastructure.scrapers.amazon_search_api import get_category_code

        # Known category
        assert get_category_code("Electronics", "Computers") == "computers"
        assert get_category_code("Electronics", "all") == "aps"

        # Unknown category defaults to aps
        assert get_category_code("Unknown", "Unknown") == "aps"
