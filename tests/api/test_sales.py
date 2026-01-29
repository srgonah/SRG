"""API smoke tests for sales endpoints."""

from datetime import date, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import (
    get_create_sales_invoice_use_case,
    get_create_sales_pdf_use_case,
    get_sales_inv_store,
)
from src.api.main import app
from src.application.use_cases.create_sales_invoice import (
    CreateSalesInvoiceResult,
    CreateSalesInvoiceUseCase,
)
from src.application.use_cases.create_sales_pdf import CreateSalesPdfUseCase, SalesPdfResult
from src.core.entities.local_sale import LocalSalesInvoice, LocalSalesItem


def _make_sample_invoice(now: datetime | None = None) -> LocalSalesInvoice:
    """Create a sample invoice for tests."""
    if now is None:
        now = datetime.utcnow()
    return LocalSalesInvoice(
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


@pytest.fixture
def mock_sales_store():
    store = AsyncMock()
    now = datetime.utcnow()
    sample_invoice = _make_sample_invoice(now)
    store.list_invoices.return_value = [sample_invoice]
    store.get_invoice.return_value = sample_invoice
    return store


@pytest.fixture
def mock_create_sales_uc():
    uc = AsyncMock(spec=CreateSalesInvoiceUseCase)
    now = datetime.utcnow()
    invoice = _make_sample_invoice(now)
    result = CreateSalesInvoiceResult(invoice=invoice)
    uc.execute.return_value = result
    uc.to_response.return_value = CreateSalesInvoiceUseCase().to_response(result)
    return uc


@pytest.fixture
def mock_sales_pdf_uc():
    """Mock sales PDF use case returning fake PDF bytes."""
    uc = Mock(spec=CreateSalesPdfUseCase)
    pdf_result = SalesPdfResult(
        pdf_bytes=b"%PDF-1.4 fake pdf content",
        invoice_id=1,
        file_path="sales_invoice_1.pdf",
        file_size=25,
    )
    uc.execute = AsyncMock(return_value=pdf_result)
    return uc


@pytest.fixture
def mock_sales_pdf_uc_not_found():
    """Mock sales PDF use case that raises ValueError."""
    uc = Mock(spec=CreateSalesPdfUseCase)
    uc.execute = AsyncMock(side_effect=ValueError("Sales invoice not found: 999"))
    return uc


@pytest.fixture
async def sales_client(mock_sales_store, mock_create_sales_uc, mock_sales_pdf_uc):
    app.dependency_overrides[get_sales_inv_store] = lambda: mock_sales_store
    app.dependency_overrides[get_create_sales_invoice_use_case] = lambda: mock_create_sales_uc
    app.dependency_overrides[get_create_sales_pdf_use_case] = lambda: mock_sales_pdf_uc
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_sales_inv_store, None)
    app.dependency_overrides.pop(get_create_sales_invoice_use_case, None)
    app.dependency_overrides.pop(get_create_sales_pdf_use_case, None)


@pytest.fixture
async def sales_client_pdf_not_found(mock_sales_store, mock_create_sales_uc, mock_sales_pdf_uc_not_found):
    app.dependency_overrides[get_sales_inv_store] = lambda: mock_sales_store
    app.dependency_overrides[get_create_sales_invoice_use_case] = lambda: mock_create_sales_uc
    app.dependency_overrides[get_create_sales_pdf_use_case] = lambda: mock_sales_pdf_uc_not_found
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_sales_inv_store, None)
    app.dependency_overrides.pop(get_create_sales_invoice_use_case, None)
    app.dependency_overrides.pop(get_create_sales_pdf_use_case, None)


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


class TestSalesPdfAPI:
    """Tests for GET /api/sales/invoices/{invoice_id}/pdf."""

    async def test_pdf_endpoint_returns_200(self, sales_client: AsyncClient):
        """Test that the PDF endpoint returns 200 with PDF content."""
        response = await sales_client.get("/api/sales/invoices/1/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "sales_invoice_1.pdf" in response.headers.get("content-disposition", "")
        assert response.content == b"%PDF-1.4 fake pdf content"

    async def test_pdf_endpoint_not_found(self, sales_client_pdf_not_found: AsyncClient):
        """Test that the PDF endpoint returns 404 for missing invoice."""
        response = await sales_client_pdf_not_found.get("/api/sales/invoices/999/pdf")
        assert response.status_code == 404
        data = response.json()
        detail = data.get("detail") or data.get("message") or ""
        assert "not found" in detail.lower()
