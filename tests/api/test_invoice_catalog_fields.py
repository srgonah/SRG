"""Tests for catalog-related fields on invoice detail endpoint."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_inv_store, get_mat_store
from src.api.main import app
from src.core.entities.invoice import Invoice, LineItem, RowType
from src.core.entities.material import Material


@pytest.fixture
def sample_invoice_with_items():
    """Invoice with mixed matched/unmatched items."""
    return Invoice(
        id=1,
        doc_id=1,
        invoice_no="INV-001",
        seller_name="ACME",
        currency="USD",
        total_amount=650.0,
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
                matched_material_id="mat-abc",
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
                matched_material_id=None,
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
def mock_inv_store(sample_invoice_with_items):
    """Mock invoice store returning the sample invoice."""
    store = AsyncMock()
    store.get_invoice = AsyncMock(return_value=sample_invoice_with_items)
    return store


@pytest.fixture
def mock_mat_store():
    """Mock material store with search results."""
    store = AsyncMock()
    store.search_by_name = AsyncMock(
        return_value=[
            Material(
                id="mat-xyz",
                name="Steel Rod Standard",
                normalized_name="steel rod standard",
                hs_code="7214.10",
                unit="KG",
            ),
        ]
    )
    return store


@pytest.fixture
async def detail_client(mock_inv_store, mock_mat_store):
    """Async client with invoice + material store overrides."""
    app.dependency_overrides[get_inv_store] = lambda: mock_inv_store
    app.dependency_overrides[get_mat_store] = lambda: mock_mat_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_inv_store, None)
    app.dependency_overrides.pop(get_mat_store, None)


class TestInvoiceCatalogFields:
    """Tests for catalog fields on GET /api/invoices/{id}."""

    async def test_matched_item_has_material_id(self, detail_client: AsyncClient):
        """Matched item shows matched_material_id and needs_catalog=False."""
        resp = await detail_client.get("/api/invoices/1")
        assert resp.status_code == 200
        items = resp.json()["line_items"]
        pvc = items[0]
        assert pvc["matched_material_id"] == "mat-abc"
        assert pvc["needs_catalog"] is False
        assert pvc["catalog_suggestions"] == []

    async def test_unmatched_item_needs_catalog(self, detail_client: AsyncClient):
        """Unmatched line item has needs_catalog=True and suggestions."""
        resp = await detail_client.get("/api/invoices/1")
        items = resp.json()["line_items"]
        steel = items[1]
        assert steel["matched_material_id"] is None
        assert steel["needs_catalog"] is True
        assert len(steel["catalog_suggestions"]) == 1
        assert steel["catalog_suggestions"][0]["material_id"] == "mat-xyz"
        assert steel["catalog_suggestions"][0]["name"] == "Steel Rod Standard"

    async def test_non_line_item_not_flagged(self, detail_client: AsyncClient):
        """Subtotal rows have needs_catalog=False."""
        resp = await detail_client.get("/api/invoices/1")
        items = resp.json()["line_items"]
        subtotal = items[2]
        assert subtotal["needs_catalog"] is False
        assert subtotal["catalog_suggestions"] == []

    async def test_suggestion_fields(self, detail_client: AsyncClient):
        """Suggestions include material_id, name, normalized_name, hs_code, unit."""
        resp = await detail_client.get("/api/invoices/1")
        items = resp.json()["line_items"]
        suggestions = items[1]["catalog_suggestions"]
        s = suggestions[0]
        assert "material_id" in s
        assert "name" in s
        assert "normalized_name" in s
        assert "hs_code" in s
        assert "unit" in s
