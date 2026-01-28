"""Tests for GenerateProformaPdfUseCase."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.use_cases.generate_proforma_pdf import GenerateProformaPdfUseCase
from src.core.entities.invoice import AuditResult, AuditStatus, Invoice
from src.core.services.proforma_pdf_service import (
    IProformaPdfRenderer,
    ProformaPdfResult,
    ProformaPdfService,
)


@pytest.fixture
def mock_renderer() -> MagicMock:
    """Create mock PDF renderer."""
    renderer = MagicMock(spec=IProformaPdfRenderer)
    renderer.render.return_value = b"%PDF-1.4 mock pdf content"
    return renderer


@pytest.fixture
def mock_invoice_store() -> AsyncMock:
    """Create mock invoice store."""
    store = AsyncMock()
    store.get_invoice.return_value = Invoice(
        id=1,
        invoice_no="INV-001",
        seller_name="Test Corp",
        buyer_name="Buyer Inc",
        total_amount=1500.0,
        items=[],
    )
    store.get_audit_result.return_value = AuditResult(
        id=1,
        invoice_id=1,
        success=True,
        status=AuditStatus.PASS,
        proforma_summary={"total": 1500},
    )
    return store


@pytest.fixture
def pdf_service(mock_renderer: MagicMock, mock_invoice_store: AsyncMock) -> ProformaPdfService:
    """Create ProformaPdfService with mocks."""
    return ProformaPdfService(
        renderer=mock_renderer,
        invoice_store=mock_invoice_store,
    )


class TestGenerateProformaPdfUseCase:
    """Tests for GenerateProformaPdfUseCase."""

    async def test_execute_success(
        self, pdf_service: ProformaPdfService, mock_renderer: MagicMock
    ):
        """Test successful PDF generation."""
        use_case = GenerateProformaPdfUseCase(pdf_service=pdf_service)
        result = await use_case.execute(invoice_id=1)

        assert isinstance(result, ProformaPdfResult)
        assert result.invoice_id == 1
        assert result.file_size > 0
        assert result.pdf_bytes == b"%PDF-1.4 mock pdf content"
        mock_renderer.render.assert_called_once()

    async def test_execute_invoice_not_found(self, mock_renderer: MagicMock):
        """Test PDF generation with missing invoice."""
        store = AsyncMock()
        store.get_invoice.return_value = None

        service = ProformaPdfService(renderer=mock_renderer, invoice_store=store)
        use_case = GenerateProformaPdfUseCase(pdf_service=service)

        with pytest.raises(ValueError, match="Invoice not found"):
            await use_case.execute(invoice_id=999)

    async def test_execute_audit_not_found(self, mock_renderer: MagicMock):
        """Test PDF generation with missing audit result."""
        store = AsyncMock()
        store.get_invoice.return_value = Invoice(
            id=1, invoice_no="INV-001", total_amount=100.0, items=[]
        )
        store.get_audit_result.return_value = None

        service = ProformaPdfService(renderer=mock_renderer, invoice_store=store)
        use_case = GenerateProformaPdfUseCase(pdf_service=service)

        with pytest.raises(ValueError, match="Audit result not found"):
            await use_case.execute(invoice_id=1)

    async def test_to_response(self, pdf_service: ProformaPdfService):
        """Test converting result to response DTO."""
        use_case = GenerateProformaPdfUseCase(pdf_service=pdf_service)
        result = await use_case.execute(invoice_id=1)

        response = use_case.to_response(result)
        assert response.invoice_id == "1"
        assert response.file_size > 0
        assert "proforma" in response.file_path
