"""
Unit tests for Amazon Import Service.

Tests deduplication logic and material creation.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.entities.material import Material, OriginConfidence
from src.core.services.amazon_import_service import AmazonImportService, ImportResult


class MockSearchResult:
    """Mock Amazon search result."""

    def __init__(
        self,
        asin: str,
        title: str,
        brand: str | None = None,
        price: str | None = None,
        price_value: float | None = None,
        currency: str | None = None,
        product_url: str = "",
    ):
        self.asin = asin
        self.title = title
        self.brand = brand
        self.price = price
        self.price_value = price_value
        self.currency = currency
        self.product_url = product_url or f"https://www.amazon.ae/dp/{asin}"
        self.rating = None
        self.reviews_count = None
        self.image_url = None
        self.is_prime = False


@pytest.fixture
def mock_store():
    """Create a mock material store."""
    store = AsyncMock()
    store.find_by_normalized_name = AsyncMock(return_value=None)
    store.find_by_synonym = AsyncMock(return_value=None)
    store.create_material = AsyncMock(side_effect=lambda m: m)
    store.add_synonym = AsyncMock()
    return store


@pytest.fixture
def service(mock_store):
    """Create an AmazonImportService with mock store."""
    return AmazonImportService(mock_store)


class TestAmazonImportService:
    """Tests for AmazonImportService."""

    @pytest.mark.asyncio
    async def test_import_new_item_success(self, service, mock_store):
        """Test importing a new item that doesn't exist."""
        # Arrange
        items = [
            MockSearchResult(
                asin="B09TEST001",
                title="Test Product XYZ",
                brand="TestBrand",
                price="AED 99.00",
                price_value=99.0,
                currency="AED",
            )
        ]

        # Act
        result = await service.import_items(items, category="Electronics")

        # Assert
        assert result.items_found == 1
        assert result.items_saved == 1
        assert result.items_skipped == 0
        assert result.items_error == 0

        assert len(result.items) == 1
        assert result.items[0].status == "saved"
        assert result.items[0].asin == "B09TEST001"

        # Verify material was created
        mock_store.create_material.assert_called_once()
        created_material = mock_store.create_material.call_args[0][0]
        assert created_material.name == "Test Product XYZ"
        assert created_material.category == "Electronics"
        assert created_material.brand == "TestBrand"
        assert created_material.origin_confidence == OriginConfidence.UNKNOWN

    @pytest.mark.asyncio
    async def test_import_duplicate_by_normalized_name(self, service, mock_store):
        """Test that duplicate by normalized name is skipped."""
        # Arrange
        existing_material = Material(
            id="existing-id-123",
            name="Test Product XYZ",
            normalized_name="test product xyz",
        )
        mock_store.find_by_normalized_name.return_value = existing_material

        items = [
            MockSearchResult(
                asin="B09TEST001",
                title="Test Product XYZ",
                brand="TestBrand",
            )
        ]

        # Act
        result = await service.import_items(items)

        # Assert
        assert result.items_found == 1
        assert result.items_saved == 0
        assert result.items_skipped == 1
        assert result.items_error == 0

        assert result.items[0].status == "skipped_duplicate"
        assert result.items[0].existing_material_id == "existing-id-123"

        # Verify no material was created
        mock_store.create_material.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_duplicate_by_synonym(self, service, mock_store):
        """Test that duplicate by synonym is skipped."""
        # Arrange
        existing_material = Material(
            id="existing-id-456",
            name="Original Product Name",
            normalized_name="original product name",
            synonyms=["Test Product XYZ"],
        )
        mock_store.find_by_normalized_name.return_value = None
        mock_store.find_by_synonym.return_value = existing_material

        items = [
            MockSearchResult(
                asin="B09TEST001",
                title="Test Product XYZ",
            )
        ]

        # Act
        result = await service.import_items(items)

        # Assert
        assert result.items_found == 1
        assert result.items_saved == 0
        assert result.items_skipped == 1

        assert result.items[0].status == "skipped_duplicate"
        assert result.items[0].existing_material_id == "existing-id-456"

    @pytest.mark.asyncio
    async def test_import_multiple_items_mixed_results(self, service, mock_store):
        """Test importing multiple items with mixed results."""
        # Arrange
        existing_material = Material(
            id="existing-id",
            name="Existing Product",
            normalized_name="existing product",
        )

        # First item is duplicate, second is new
        async def find_by_name(name: str):
            if name == "existing product":
                return existing_material
            return None

        mock_store.find_by_normalized_name.side_effect = find_by_name

        items = [
            MockSearchResult(asin="B09TEST001", title="Existing Product"),
            MockSearchResult(asin="B09TEST002", title="New Product ABC"),
        ]

        # Act
        result = await service.import_items(items, category="Tools")

        # Assert
        assert result.items_found == 2
        assert result.items_saved == 1
        assert result.items_skipped == 1
        assert result.items_error == 0

        # Verify correct items
        assert result.items[0].status == "skipped_duplicate"
        assert result.items[1].status == "saved"

    @pytest.mark.asyncio
    async def test_import_with_unit(self, service, mock_store):
        """Test that unit is applied to imported materials."""
        # Arrange
        items = [MockSearchResult(asin="B09TEST001", title="Test Item")]

        # Act
        await service.import_items(items, category="Industrial", unit="PCS")

        # Assert
        created_material = mock_store.create_material.call_args[0][0]
        assert created_material.unit == "PCS"

    @pytest.mark.asyncio
    async def test_import_brand_added_as_synonym(self, service, mock_store):
        """Test that brand is added as a synonym."""
        # Arrange
        def create_with_id(m):
            m.id = "new-id-123"
            return m

        mock_store.create_material.side_effect = create_with_id

        items = [
            MockSearchResult(
                asin="B09TEST001",
                title="Widget Pro",
                brand="Acme Corp",
            )
        ]

        # Act
        await service.import_items(items)

        # Assert
        mock_store.add_synonym.assert_called_once_with("new-id-123", "Acme Corp")

    @pytest.mark.asyncio
    async def test_import_empty_list(self, service, mock_store):
        """Test importing an empty list."""
        # Act
        result = await service.import_items([])

        # Assert
        assert result.items_found == 0
        assert result.items_saved == 0
        assert result.items_skipped == 0
        assert result.items_error == 0
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_import_origin_confidence_unknown(self, service, mock_store):
        """Test that origin confidence is always set to unknown."""
        # Arrange
        items = [MockSearchResult(asin="B09TEST001", title="Test Item")]

        # Act
        await service.import_items(items)

        # Assert
        created_material = mock_store.create_material.call_args[0][0]
        assert created_material.origin_confidence == OriginConfidence.UNKNOWN
        assert created_material.origin_country is None

    @pytest.mark.asyncio
    async def test_import_error_handling(self, service, mock_store):
        """Test that errors are caught and reported."""
        # Arrange
        mock_store.find_by_normalized_name.side_effect = Exception("Database error")

        items = [MockSearchResult(asin="B09TEST001", title="Test Item")]

        # Act
        result = await service.import_items(items)

        # Assert
        assert result.items_found == 1
        assert result.items_saved == 0
        assert result.items_skipped == 0
        assert result.items_error == 1

        assert result.items[0].status == "error"
        assert "Database error" in result.items[0].error_message

    @pytest.mark.asyncio
    async def test_import_description_built_from_metadata(self, service, mock_store):
        """Test that description is built from item metadata."""
        # Arrange
        items = [
            MockSearchResult(
                asin="B09TEST001",
                title="Test Item",
                brand="TestBrand",
                price="AED 50.00",
            )
        ]
        items[0].rating = 4.5
        items[0].reviews_count = 100

        # Act
        await service.import_items(items)

        # Assert
        created_material = mock_store.create_material.call_args[0][0]
        assert "Brand: TestBrand" in created_material.description
        assert "Reference price: AED 50.00" in created_material.description
        assert "Rating: 4.5/5" in created_material.description
        assert "Reviews: 100" in created_material.description
