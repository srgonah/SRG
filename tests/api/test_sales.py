"""API smoke tests for sales endpoints."""

from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_create_sales_invoice_use_case, get_sales_inv_store
from src.api.main import app
from src.application.use_cases.create_sales_invoice import (
    CreateSalesInvoiceResult,
    CreateSalesInvoiceUseCase,
)
from src.core.entities.local_sale import LocalSalesInvoice, LocalSalesItem


@pytest.fixture
def mock_sales_store():
    store = AsyncMock()
    now = datetime.utcnow()
    sample_invoice = LocalSalesInvoice(
        id=1, invoice_number="LS-001", customer_name="Test",
        sale_date=date.today(),
        items=[
            LocalSalesItem(
                id=1, sales_invoice_id=1, inventory_item_id=1,
                material_id="MAT-001", description="Cable",
                quantity=10, unit_price=15, cost_basis=100,
                created_at=now,
            ),
        ],
        created_at=now, updated_at=now,
    )
    store.list_invoices.return_value = [sample_invoice]
    store.get_invoice.return_value = sample_invoice
    return store


@pytest.fixture
def mock_create_sales_uc():
    uc = AsyncMock(spec=CreateSalesInvoiceUseCase)
    now = datetime.utcnow()
    invoice = LocalSalesInvoice(
        id=1, invoice_number="LS-001", customer_name="Test",
        sale_date=date.today(),
        items=[
            LocalSalesItem(
                id=1, sales_invoice_id=1, inventory_item_id=1,
                material_id="MAT-001", description="Cable",
                quantity=10, unit_price=15, cost_basis=100,
                created_at=now,
            ),
        ],
        created_at=now, updated_at=now,
    )
    result = CreateSalesInvoiceResult(invoice=invoice)
    uc.execute.return_value = result
    uc.to_response.return_value = CreateSalesInvoiceUseCase().to_response(result)
    return uc


@pytest.fixture
async def sales_client(mock_sales_store, mock_create_sales_uc):
    app.dependency_overrides[get_sales_inv_store] = lambda: mock_sales_store
    app.dependency_overrides[get_create_sales_invoice_use_case] = lambda: mock_create_sales_uc
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_sales_inv_store, None)
    app.dependency_overrides.pop(get_create_sales_invoice_use_case, None)


class TestSalesAPI:
    async def test_create_invoice_endpoint_exists(self, sales_client: AsyncClient):
        response = await sales_client.post(
            "/api/sales/invoices",
            json={
                "invoice_number": "LS-001",
                "customer_name": "Test",
                "items": [
                    {"material_id": "MAT-001", "description": "Cable", "quantity": 10, "unit_price": 15},
                ],
            },
        )
        assert response.status_code != 404

    async def test_create_returns_201(self, sales_client: AsyncClient):
        response = await sales_client.post(
            "/api/sales/invoices",
            json={
                "invoice_number": "LS-001",
                "customer_name": "Test",
                "items": [
                    {"material_id": "MAT-001", "description": "Cable", "quantity": 10, "unit_price": 15},
                ],
            },
        )
        assert response.status_code == 201

    async def test_list_endpoint_exists(self, sales_client: AsyncClient):
        response = await sales_client.get("/api/sales/invoices")
        assert response.status_code != 404

    async def test_get_by_id_endpoint_exists(self, sales_client: AsyncClient):
        response = await sales_client.get("/api/sales/invoices/1")
        assert response.status_code != 404
