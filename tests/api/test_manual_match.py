"""API tests for manual match endpoint."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_inv_store, get_mat_store
from src.api.main import app
from src.core.entities.invoice import Invoice, LineItem, RowType
from src.core.entities.material import Material


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
                quantity=100,
                unit_price=5.0,
                total_price=500.0,
                row_type=RowType.LINE_ITEM,
            ),
        ],
    )


@pytest.fixture
def mock_invoice_store(sample_invoice):
    """Create mock invoice store."""
    store = AsyncMock()
    store.get_invoice = AsyncMock(return_value=sample_invoice)
    store.get_invoice_item = AsyncMock(
        return_value={
            "id": 10,
            "invoice_id": 1,
            "line_number": 1,
            "item_name": "PVC Cable 10mm",
            "description": None,
            "hs_code": None,
            "unit": None,
            "brand": None,
            "model": None,
            "quantity": 100,
            "unit_price": 5.0,
            "total_price": 500.0,
            "row_type": "line_item",
            "matched_material_id": None,
        }
    )
    store.update_item_material_id = AsyncMock(return_value=True)
    return store


@pytest.fixture
def mock_material_store():
    """Create mock material store."""
    store = AsyncMock()
    mat = Material(
        id="mat-abc",
        name="PVC Cable 10mm",
        normalized_name="pvc cable 10mm",
    )
    store.get_material = AsyncMock(return_value=mat)
    return store


@pytest.fixture
async def manual_match_client(mock_invoice_store, mock_material_store):
    """Async client with invoice/material dependencies overridden."""
    app.dependency_overrides[get_inv_store] = lambda: mock_invoice_store
    app.dependency_overrides[get_mat_store] = lambda: mock_material_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_inv_store, None)
    app.dependency_overrides.pop(get_mat_store, None)


@pytest.mark.asyncio
class TestManualMatchAPI:
    """Tests for POST /api/invoices/{id}/items/{item_id}/match."""

    async def test_manual_match_endpoint_exists(self, manual_match_client: AsyncClient):
        """Test that the manual match endpoint exists."""
        response = await manual_match_client.post(
            "/api/invoices/1/items/10/match",
            json={"material_id": "mat-abc"},
        )
        assert response.status_code != 404

    async def test_manual_match_returns_updated_item(
        self, manual_match_client: AsyncClient
    ):
        """Test that manual match returns the updated item data."""
        response = await manual_match_client.post(
            "/api/invoices/1/items/10/match",
            json={"material_id": "mat-abc"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["item_id"] == 10
        assert data["invoice_id"] == 1
        assert data["matched_material_id"] == "mat-abc"
        assert data["material_name"] == "PVC Cable 10mm"

    async def test_manual_match_calls_update(
        self, manual_match_client: AsyncClient, mock_invoice_store
    ):
        """Test that the store update method is called."""
        await manual_match_client.post(
            "/api/invoices/1/items/10/match",
            json={"material_id": "mat-abc"},
        )
        mock_invoice_store.update_item_material_id.assert_awaited_once_with(
            10, "mat-abc"
        )

    async def test_manual_match_invoice_not_found(
        self, mock_invoice_store, mock_material_store
    ):
        """Test 404 when invoice does not exist."""
        mock_invoice_store.get_invoice = AsyncMock(return_value=None)
        app.dependency_overrides[get_inv_store] = lambda: mock_invoice_store
        app.dependency_overrides[get_mat_store] = lambda: mock_material_store
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/invoices/999/items/10/match",
                json={"material_id": "mat-abc"},
            )
        app.dependency_overrides.pop(get_inv_store, None)
        app.dependency_overrides.pop(get_mat_store, None)
        assert response.status_code == 404

    async def test_manual_match_item_not_found(
        self, mock_invoice_store, mock_material_store
    ):
        """Test 404 when invoice item does not exist."""
        mock_invoice_store.get_invoice_item = AsyncMock(return_value=None)
        app.dependency_overrides[get_inv_store] = lambda: mock_invoice_store
        app.dependency_overrides[get_mat_store] = lambda: mock_material_store
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/invoices/1/items/999/match",
                json={"material_id": "mat-abc"},
            )
        app.dependency_overrides.pop(get_inv_store, None)
        app.dependency_overrides.pop(get_mat_store, None)
        assert response.status_code == 404

    async def test_manual_match_material_not_found(
        self, mock_invoice_store, mock_material_store
    ):
        """Test 404 when material does not exist."""
        mock_material_store.get_material = AsyncMock(return_value=None)
        app.dependency_overrides[get_inv_store] = lambda: mock_invoice_store
        app.dependency_overrides[get_mat_store] = lambda: mock_material_store
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/invoices/1/items/10/match",
                json={"material_id": "nonexistent"},
            )
        app.dependency_overrides.pop(get_inv_store, None)
        app.dependency_overrides.pop(get_mat_store, None)
        assert response.status_code == 404

    async def test_manual_match_item_wrong_invoice(
        self, mock_invoice_store, mock_material_store
    ):
        """Test 404 when item does not belong to the specified invoice."""
        mock_invoice_store.get_invoice_item = AsyncMock(
            return_value={
                "id": 10,
                "invoice_id": 99,  # different invoice
                "line_number": 1,
                "item_name": "PVC Cable 10mm",
                "description": None,
                "hs_code": None,
                "unit": None,
                "brand": None,
                "model": None,
                "quantity": 100,
                "unit_price": 5.0,
                "total_price": 500.0,
                "row_type": "line_item",
                "matched_material_id": None,
            }
        )
        app.dependency_overrides[get_inv_store] = lambda: mock_invoice_store
        app.dependency_overrides[get_mat_store] = lambda: mock_material_store
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/invoices/1/items/10/match",
                json={"material_id": "mat-abc"},
            )
        app.dependency_overrides.pop(get_inv_store, None)
        app.dependency_overrides.pop(get_mat_store, None)
        assert response.status_code == 404

    async def test_manual_match_requires_material_id(
        self, manual_match_client: AsyncClient
    ):
        """Test 422 when material_id is missing from request body."""
        response = await manual_match_client.post(
            "/api/invoices/1/items/10/match",
            json={},
        )
        assert response.status_code == 422
