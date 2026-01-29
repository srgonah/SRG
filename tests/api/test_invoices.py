"""Tests for invoice endpoints."""

import io
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_add_to_catalog_use_case, get_inv_store
from src.api.main import app
from src.application.use_cases.add_to_catalog import AutoMatchResult
from src.core.entities.invoice import Invoice, LineItem, RowType


def test_list_invoices(client: TestClient, api_prefix: str):
    """Test listing invoices."""
    response = client.get(f"{api_prefix}/invoices")

    # Should work even with empty database
    assert response.status_code == 200

    data = response.json()
    assert "invoices" in data
    assert "total" in data
    assert isinstance(data["invoices"], list)


def test_list_invoices_pagination(client: TestClient, api_prefix: str):
    """Test invoice list pagination."""
    response = client.get(f"{api_prefix}/invoices?limit=5&offset=0")
    assert response.status_code == 200

    data = response.json()
    assert data["limit"] == 5
    assert data["offset"] == 0


def test_get_invoice_not_found(client: TestClient, api_prefix: str):
    """Test getting non-existent invoice."""
    response = client.get(f"{api_prefix}/invoices/non-existent-id")
    assert response.status_code == 404


def test_upload_invoice_invalid_file_type(client: TestClient, api_prefix: str):
    """Test uploading invalid file type."""
    file_content = b"test content"
    files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}

    response = client.post(f"{api_prefix}/invoices/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file type" in (data.get("message") or data.get("error") or data.get("detail") or "")


def test_upload_invoice_empty_file(client: TestClient, api_prefix: str):
    """Test uploading empty file."""
    files = {"file": ("test.pdf", io.BytesIO(b""), "application/pdf")}

    response = client.post(f"{api_prefix}/invoices/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "Empty file" in (data.get("message") or data.get("error") or data.get("detail") or "")


def test_delete_invoice_not_found(client: TestClient, api_prefix: str):
    """Test deleting non-existent invoice."""
    response = client.delete(f"{api_prefix}/invoices/non-existent-id")
    assert response.status_code == 404


# --- Match-catalog endpoint tests ---


@pytest.fixture
def mock_invoice_store_for_match():
    """Create mock invoice store with a sample invoice."""
    store = AsyncMock()
    sample_invoice = Invoice(
        id=1,
        invoice_no="INV-001",
        seller_name="Seller Co",
        buyer_name="Buyer Co",
        total_amount=1000.0,
        currency="USD",
        items=[
            LineItem(
                id=10,
                invoice_id=1,
                item_name="PVC Cable 10mm",
                description="PVC Cable 10mm",
                quantity=5,
                unit_price=100.0,
                total_price=500.0,
                row_type=RowType.LINE_ITEM,
            ),
            LineItem(
                id=11,
                invoice_id=1,
                item_name="Copper Wire",
                description="Copper Wire",
                quantity=3,
                unit_price=166.67,
                total_price=500.0,
                row_type=RowType.LINE_ITEM,
            ),
        ],
    )
    store.get_invoice.return_value = sample_invoice
    return store


@pytest.fixture
def mock_invoice_store_not_found():
    """Create mock invoice store that returns None."""
    store = AsyncMock()
    store.get_invoice.return_value = None
    return store


@pytest.fixture
def mock_catalog_match_uc():
    """Create mock AddToCatalogUseCase with auto_match results."""
    uc = Mock()
    result = AutoMatchResult(
        matched=1,
        unmatched=1,
        matches=[(10, "mat-abc")],
    )
    uc.auto_match_items = AsyncMock(return_value=result)
    return uc


@pytest.fixture
async def match_client(mock_invoice_store_for_match, mock_catalog_match_uc):
    """Async client with match-catalog dependencies overridden."""
    app.dependency_overrides[get_inv_store] = lambda: mock_invoice_store_for_match
    app.dependency_overrides[get_add_to_catalog_use_case] = lambda: mock_catalog_match_uc
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_inv_store, None)
    app.dependency_overrides.pop(get_add_to_catalog_use_case, None)


@pytest.fixture
async def match_client_not_found(mock_invoice_store_not_found, mock_catalog_match_uc):
    """Async client where invoice is not found."""
    app.dependency_overrides[get_inv_store] = lambda: mock_invoice_store_not_found
    app.dependency_overrides[get_add_to_catalog_use_case] = lambda: mock_catalog_match_uc
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_inv_store, None)
    app.dependency_overrides.pop(get_add_to_catalog_use_case, None)


class TestMatchCatalog:
    """Tests for POST /api/invoices/{invoice_id}/match-catalog."""

    async def test_match_catalog_returns_200(self, match_client: AsyncClient):
        """Test that match-catalog returns 200 with match results."""
        response = await match_client.post("/api/invoices/1/match-catalog")
        assert response.status_code == 200
        data = response.json()
        assert data["invoice_id"] == "1"
        assert data["matched"] == 1
        assert data["unmatched"] == 1
        assert data["total_items"] == 2
        assert len(data["results"]) == 2

        # First item should be matched
        matched_items = [r for r in data["results"] if r["matched"]]
        assert len(matched_items) == 1
        assert matched_items[0]["material_id"] == "mat-abc"

    async def test_match_catalog_not_found(self, match_client_not_found: AsyncClient):
        """Test that match-catalog returns 404 for non-existent invoice."""
        response = await match_client_not_found.post("/api/invoices/999/match-catalog")
        assert response.status_code == 404
        data = response.json()
        detail = data.get("detail") or data.get("message") or ""
        assert "not found" in detail.lower()

    async def test_match_catalog_invalid_id(self, match_client: AsyncClient):
        """Test that match-catalog returns 404 for non-numeric invoice ID."""
        response = await match_client.post("/api/invoices/abc/match-catalog")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Proforma preview endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_proforma_pdf_uc():
    """Mock proforma PDF use case returning fake PDF bytes."""
    from src.application.use_cases.generate_proforma_pdf import GenerateProformaPdfUseCase
    from src.core.services.proforma_pdf_service import ProformaPdfResult

    uc = Mock(spec=GenerateProformaPdfUseCase)
    pdf_result = ProformaPdfResult(
        pdf_bytes=b"%PDF-1.4 fake proforma preview",
        invoice_id=1,
        file_path="proforma_1.pdf",
        file_size=31,
    )
    uc.execute = AsyncMock(return_value=pdf_result)
    return uc


@pytest.fixture
def mock_proforma_pdf_uc_not_found():
    """Mock proforma PDF use case that raises ValueError."""
    from src.application.use_cases.generate_proforma_pdf import GenerateProformaPdfUseCase

    uc = Mock(spec=GenerateProformaPdfUseCase)
    uc.execute = AsyncMock(side_effect=ValueError("Invoice not found: 999"))
    return uc


@pytest.fixture
async def preview_client(mock_proforma_pdf_uc):
    """Async client with mocked proforma PDF use case."""
    from src.api.dependencies import get_generate_proforma_pdf_use_case

    app.dependency_overrides[get_generate_proforma_pdf_use_case] = lambda: mock_proforma_pdf_uc
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_generate_proforma_pdf_use_case, None)


@pytest.fixture
async def preview_client_not_found(mock_proforma_pdf_uc_not_found):
    """Async client with mocked proforma PDF use case that raises 404."""
    from src.api.dependencies import get_generate_proforma_pdf_use_case

    app.dependency_overrides[get_generate_proforma_pdf_use_case] = lambda: mock_proforma_pdf_uc_not_found
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_generate_proforma_pdf_use_case, None)


class TestProformaPreview:
    """Tests for POST /api/invoices/{id}/proforma-preview."""

    @pytest.mark.asyncio
    async def test_preview_returns_pdf_bytes(self, preview_client: AsyncClient):
        """Test that proforma-preview returns PDF bytes with inline disposition."""
        response = await preview_client.post("/api/invoices/1/proforma-preview")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "inline" in response.headers.get("content-disposition", "")
        assert response.content == b"%PDF-1.4 fake proforma preview"

    @pytest.mark.asyncio
    async def test_preview_not_found(self, preview_client_not_found: AsyncClient):
        """Test that proforma-preview returns 404 for missing invoice."""
        response = await preview_client_not_found.post("/api/invoices/999/proforma-preview")
        assert response.status_code == 404
        data = response.json()
        detail = data.get("detail") or data.get("message") or ""
        assert "not found" in detail.lower()
