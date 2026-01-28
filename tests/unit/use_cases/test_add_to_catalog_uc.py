"""Unit tests for AddToCatalogUseCase."""

from unittest.mock import AsyncMock

import pytest

from src.application.dto.requests import AddToCatalogRequest
from src.application.use_cases.add_to_catalog import AddToCatalogUseCase
from src.core.entities.invoice import Invoice, LineItem, RowType
from src.core.entities.material import Material
from src.core.exceptions import InvoiceNotFoundError


@pytest.fixture
def mock_invoice_store():
    """Create a mock invoice store."""
    store = AsyncMock()
    store.update_item_material_id = AsyncMock(return_value=True)
    return store


@pytest.fixture
def mock_material_store():
    """Create a mock material store."""
    store = AsyncMock()
    store.find_by_normalized_name = AsyncMock(return_value=None)
    store.find_by_synonym = AsyncMock(return_value=None)
    return store


@pytest.fixture
def mock_price_store():
    """Create a mock price history store."""
    store = AsyncMock()
    store.link_material = AsyncMock(return_value=1)
    return store


@pytest.fixture
def sample_invoice():
    """Invoice with line items for testing."""
    return Invoice(
        id=1,
        doc_id=1,
        invoice_no="INV-001",
        seller_name="ACME Corp",
        currency="USD",
        items=[
            LineItem(
                id=10,
                invoice_id=1,
                line_number=1,
                item_name="PVC Cable 10mm",
                hs_code="8544.42",
                unit="M",
                quantity=100,
                unit_price=5.0,
                total_price=500.0,
                row_type=RowType.LINE_ITEM,
            ),
            LineItem(
                id=11,
                invoice_id=1,
                line_number=2,
                item_name="Steel Rod 12mm",
                hs_code="7214.10",
                unit="KG",
                quantity=50,
                unit_price=3.0,
                total_price=150.0,
                row_type=RowType.LINE_ITEM,
            ),
            LineItem(
                id=12,
                invoice_id=1,
                line_number=3,
                item_name="Subtotal",
                quantity=0,
                unit_price=0,
                total_price=650.0,
                row_type=RowType.SUBTOTAL,
            ),
        ],
    )


@pytest.fixture
def use_case(mock_invoice_store, mock_material_store, mock_price_store):
    """Create use case with mocked stores."""
    return AddToCatalogUseCase(
        invoice_store=mock_invoice_store,
        material_store=mock_material_store,
        price_store=mock_price_store,
    )


@pytest.mark.asyncio
class TestAddToCatalogUseCase:
    """Tests for AddToCatalogUseCase."""

    async def test_creates_new_materials(
        self, use_case, mock_invoice_store, mock_material_store, sample_invoice
    ):
        """Creates new materials for unknown items."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        # Mock create_material to assign IDs
        call_count = 0

        async def mock_create(material):
            nonlocal call_count
            call_count += 1
            material.id = f"mat-{call_count}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        request = AddToCatalogRequest(invoice_id=1)
        result = await use_case.execute(request)

        # Only LINE_ITEM rows should be processed (not SUBTOTAL)
        assert result.materials_created == 2
        assert result.materials_updated == 0
        assert len(result.materials) == 2
        assert mock_material_store.create_material.call_count == 2

    async def test_updates_existing_material(
        self, use_case, mock_invoice_store, mock_material_store, sample_invoice
    ):
        """Updates existing material when found by normalized name."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        existing = Material(
            id="mat-100", name="PVC Cable 10mm", normalized_name="pvc cable 10mm",
            hs_code="8544.42", unit="M",
        )
        # First item found, second not found
        mock_material_store.find_by_normalized_name = AsyncMock(
            side_effect=[existing, None]
        )

        call_count = [0]

        async def mock_create(material):
            call_count[0] += 1
            material.id = f"mat-{200 + call_count[0]}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        request = AddToCatalogRequest(invoice_id=1)
        result = await use_case.execute(request)

        assert result.materials_updated == 1
        assert result.materials_created == 1
        assert len(result.materials) == 2

    async def test_links_price_history(
        self, use_case, mock_invoice_store, mock_material_store, mock_price_store, sample_invoice
    ):
        """Links price history after creating materials."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        call_count = [0]

        async def mock_create(material):
            call_count[0] += 1
            material.id = f"mat-{call_count[0]}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        request = AddToCatalogRequest(invoice_id=1)
        await use_case.execute(request)

        # link_material called for each LINE_ITEM
        assert mock_price_store.link_material.call_count == 2

    async def test_sets_matched_material_id(
        self, use_case, mock_invoice_store, mock_material_store, sample_invoice
    ):
        """Sets matched_material_id on each processed invoice item."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        call_count = [0]

        async def mock_create(material):
            call_count[0] += 1
            material.id = f"mat-{call_count[0]}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        request = AddToCatalogRequest(invoice_id=1)
        await use_case.execute(request)

        # update_item_material_id called for each LINE_ITEM
        assert mock_invoice_store.update_item_material_id.call_count == 2
        # Check it was called with correct item IDs
        calls = mock_invoice_store.update_item_material_id.call_args_list
        assert calls[0].args == (10, "mat-1")
        assert calls[1].args == (11, "mat-2")

    async def test_filters_by_item_ids(
        self, use_case, mock_invoice_store, mock_material_store, sample_invoice
    ):
        """Only processes specified item_ids when provided."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=sample_invoice)

        call_count = [0]

        async def mock_create(material):
            call_count[0] += 1
            material.id = f"mat-{call_count[0]}"
            return material

        mock_material_store.create_material = AsyncMock(side_effect=mock_create)

        request = AddToCatalogRequest(invoice_id=1, item_ids=[10])
        result = await use_case.execute(request)

        assert result.materials_created == 1
        assert result.materials[0].name == "PVC Cable 10mm"

    async def test_raises_for_nonexistent_invoice(
        self, use_case, mock_invoice_store
    ):
        """Raises InvoiceNotFoundError for missing invoice."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=None)

        request = AddToCatalogRequest(invoice_id=999)
        with pytest.raises(InvoiceNotFoundError):
            await use_case.execute(request)

    async def test_to_response(self, use_case):
        """to_response converts result to API response."""
        from src.application.use_cases.add_to_catalog import AddToCatalogResult

        result = AddToCatalogResult(
            materials_created=1,
            materials_updated=0,
            materials=[
                Material(id="mat-1", name="Widget A", hs_code="1234"),
            ],
        )
        response = use_case.to_response(result)
        assert response.materials_created == 1
        assert response.materials_updated == 0
        assert len(response.materials) == 1
        assert response.materials[0].name == "Widget A"
