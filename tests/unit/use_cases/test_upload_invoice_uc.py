"""
Unit tests for UploadInvoiceUseCase.

Tests the invoice upload flow with mocked services and stores.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.dto.requests import UploadInvoiceRequest
from src.application.use_cases.upload_invoice import UploadInvoiceUseCase, UploadResult
from src.core.entities.document import Document
from src.core.entities.invoice import AuditResult, Invoice, LineItem


# Test fixtures
@pytest.fixture
def sample_invoice() -> Invoice:
    """Create a sample invoice for testing."""
    return Invoice(
        id=123,
        invoice_no="INV-2024-001",
        seller_name="Test Vendor",
        invoice_date=datetime(2024, 1, 15).date(),
        items=[
            LineItem(
                item_name="Test Product",
                quantity=10,
                unit_price=100.0,
                total_price=1000.0,
            ),
            LineItem(
                item_name="Another Product",
                quantity=5,
                unit_price=50.0,
                total_price=250.0,
            ),
        ],
        total_amount=1250.0,
        currency="USD",
    )


@pytest.fixture
def sample_document() -> Document:
    """Create a sample document for testing."""
    return Document(
        id=456,
        filename="test_invoice.pdf",
        original_filename="test_invoice.pdf",
        file_path="/tmp/test_invoice.pdf",
        file_size=12345,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_audit_result() -> AuditResult:
    """Create a sample audit result for testing."""
    return AuditResult(
        id=789,
        invoice_id=123,
        passed=True,
        confidence=0.95,
        issues=[],
        audited_at=datetime.now(),
    )


@pytest.fixture
def mock_parser_service():
    """Create a mock parser service."""
    mock = MagicMock()
    mock.parse_invoice = AsyncMock()
    mock.validate_invoice = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_auditor_service():
    """Create a mock auditor service."""
    mock = MagicMock()
    mock.audit_invoice = AsyncMock()
    return mock


@pytest.fixture
def mock_indexer_service():
    """Create a mock indexer service."""
    mock = MagicMock()
    mock.index_document = AsyncMock()
    return mock


@pytest.fixture
def mock_invoice_store():
    """Create a mock invoice store."""
    mock = MagicMock()
    mock.save_invoice = AsyncMock()
    mock.save_audit_result = AsyncMock()
    return mock


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    mock = MagicMock()
    mock.get_pages_by_document = AsyncMock(return_value=[])
    return mock


class TestUploadInvoiceUseCase:
    """Tests for UploadInvoiceUseCase."""

    @pytest.mark.asyncio
    async def test_execute_success_with_audit(
        self,
        sample_invoice,
        sample_document,
        sample_audit_result,
        mock_parser_service,
        mock_auditor_service,
        mock_indexer_service,
        mock_invoice_store,
        mock_document_store,
    ):
        """Test successful upload with auto-audit enabled."""
        # Setup mocks
        mock_indexer_service.index_document.return_value = sample_document
        mock_parser_service.parse_invoice.return_value = sample_invoice
        mock_auditor_service.audit_invoice.return_value = sample_audit_result

        # Create use case with mocked services
        use_case = UploadInvoiceUseCase(
            parser_service=mock_parser_service,
            auditor_service=mock_auditor_service,
            indexer_service=mock_indexer_service,
            invoice_store=mock_invoice_store,
            document_store=mock_document_store,
        )

        # Execute
        request = UploadInvoiceRequest(auto_audit=True)
        result = await use_case.execute(
            file_content=b"fake pdf content",
            filename="test_invoice.pdf",
            request=request,
        )

        # Assertions
        assert isinstance(result, UploadResult)
        assert result.invoice == sample_invoice
        assert result.document == sample_document
        assert result.audit_result == sample_audit_result
        assert result.warnings == []

        # Verify service calls
        mock_indexer_service.index_document.assert_called_once()
        mock_invoice_store.save_invoice.assert_called_once()
        mock_auditor_service.audit_invoice.assert_called_once()
        mock_invoice_store.save_audit_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_success_without_audit(
        self,
        sample_invoice,
        sample_document,
        mock_parser_service,
        mock_indexer_service,
        mock_invoice_store,
        mock_document_store,
    ):
        """Test successful upload with auto-audit disabled."""
        # Setup mocks
        mock_indexer_service.index_document.return_value = sample_document
        mock_parser_service.parse_invoice.return_value = sample_invoice

        # Create use case without auditor
        use_case = UploadInvoiceUseCase(
            parser_service=mock_parser_service,
            auditor_service=None,  # No auditor
            indexer_service=mock_indexer_service,
            invoice_store=mock_invoice_store,
            document_store=mock_document_store,
        )

        # Execute with audit disabled
        request = UploadInvoiceRequest(auto_audit=False)
        result = await use_case.execute(
            file_content=b"fake pdf content",
            filename="test_invoice.pdf",
            request=request,
        )

        # Assertions
        assert result.invoice == sample_invoice
        assert result.document == sample_document
        assert result.audit_result is None

    @pytest.mark.asyncio
    async def test_execute_with_vendor_hint(
        self,
        sample_invoice,
        sample_document,
        mock_parser_service,
        mock_indexer_service,
        mock_invoice_store,
        mock_document_store,
    ):
        """Test upload with vendor hint passed to indexer."""
        # Setup mocks
        mock_indexer_service.index_document.return_value = sample_document
        mock_parser_service.parse_invoice.return_value = sample_invoice

        # Create use case
        use_case = UploadInvoiceUseCase(
            parser_service=mock_parser_service,
            indexer_service=mock_indexer_service,
            invoice_store=mock_invoice_store,
            document_store=mock_document_store,
        )

        # Execute with vendor hint
        request = UploadInvoiceRequest(
            vendor_hint="VOLTA HUB",
            template_id="volta_hub",
            auto_audit=False,
        )
        await use_case.execute(
            file_content=b"fake pdf content",
            filename="volta_invoice.pdf",
            request=request,
        )

        # Verify vendor hint was passed to indexer
        call_kwargs = mock_indexer_service.index_document.call_args
        assert call_kwargs[1]["metadata"]["vendor_hint"] == "VOLTA HUB"
        assert call_kwargs[1]["metadata"]["template_id"] == "volta_hub"

    @pytest.mark.asyncio
    async def test_execute_with_warnings(
        self,
        sample_invoice,
        sample_document,
        mock_parser_service,
        mock_indexer_service,
        mock_invoice_store,
        mock_document_store,
    ):
        """Test upload that produces validation warnings."""
        # Setup mocks
        mock_indexer_service.index_document.return_value = sample_document
        mock_parser_service.parse_invoice.return_value = sample_invoice
        mock_parser_service.validate_invoice.return_value = [
            "Missing invoice number",
            "Line 2 total mismatch",
        ]

        # Create use case
        use_case = UploadInvoiceUseCase(
            parser_service=mock_parser_service,
            indexer_service=mock_indexer_service,
            invoice_store=mock_invoice_store,
            document_store=mock_document_store,
        )

        # Execute
        request = UploadInvoiceRequest(auto_audit=False)
        result = await use_case.execute(
            file_content=b"fake pdf content",
            filename="test_invoice.pdf",
            request=request,
        )

        # Verify warnings are returned
        assert len(result.warnings) == 2
        assert "Missing invoice number" in result.warnings

    def test_to_response_format(
        self,
        sample_invoice,
        sample_document,
        sample_audit_result,
    ):
        """Test conversion to API response format."""
        # Create result
        result = UploadResult(
            invoice=sample_invoice,
            document=sample_document,
            audit_result=sample_audit_result,
            warnings=["Test warning"],
        )

        # Create use case and convert
        use_case = UploadInvoiceUseCase()
        response = use_case.to_response(result)

        # Verify response structure
        assert "invoice" in response
        assert "document_id" in response
        assert "warnings" in response
        assert "audit" in response
        assert response["document_id"] == 456  # Integer ID
        assert response["warnings"] == ["Test warning"]

    @pytest.mark.asyncio
    async def test_upload_from_path_file_not_found(self):
        """Test upload_from_path with non-existent file."""
        use_case = UploadInvoiceUseCase()

        with pytest.raises(FileNotFoundError):
            await use_case.upload_from_path("/non/existent/file.pdf")


class TestUploadInvoiceRequestValidation:
    """Tests for UploadInvoiceRequest DTO validation."""

    def test_valid_request(self):
        """Test valid request creation."""
        request = UploadInvoiceRequest(
            vendor_hint="Test Vendor",
            template_id="test_template",
            auto_audit=True,
        )
        assert request.vendor_hint == "Test Vendor"
        assert request.template_id == "test_template"
        assert request.auto_audit is True

    def test_default_values(self):
        """Test default values are applied."""
        request = UploadInvoiceRequest()
        assert request.vendor_hint is None
        assert request.template_id is None
        assert request.auto_audit is True
        assert request.auto_index is True
        assert request.strict_mode is False

    def test_optional_fields(self):
        """Test optional fields can be None."""
        request = UploadInvoiceRequest(
            vendor_hint=None,
            template_id=None,
            source=None,
        )
        assert request.vendor_hint is None
        assert request.template_id is None
        assert request.source is None
