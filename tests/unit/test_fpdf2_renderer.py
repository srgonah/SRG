"""Tests for Fpdf2ProformaRenderer."""


import pytest

from src.core.entities.invoice import (
    AuditResult,
    AuditStatus,
    BankDetails,
    Invoice,
    LineItem,
    RowType,
)
from src.infrastructure.pdf.fpdf2_renderer import Fpdf2ProformaRenderer


@pytest.fixture
def renderer() -> Fpdf2ProformaRenderer:
    """Create renderer instance."""
    return Fpdf2ProformaRenderer()


@pytest.fixture
def sample_invoice() -> Invoice:
    """Create sample invoice for PDF generation."""
    return Invoice(
        id=1,
        invoice_no="INV-2026-001",
        invoice_date="2026-01-15",
        seller_name="ACME Corp",
        buyer_name="Test Buyer Inc",
        currency="USD",
        total_amount=1500.00,
        subtotal=1400.00,
        tax_amount=100.00,
        discount_amount=0.0,
        bank_details=BankDetails(
            beneficiary_name="ACME Corp",
            bank_name="First National",
            account_number="123456789",
            iban="US12345678901234",
            swift="ACMEUS33",
        ),
        items=[
            LineItem(
                line_number=1,
                item_name="Widget A",
                description="Premium widget model A",
                unit="PCS",
                quantity=5,
                unit_price=200.00,
                total_price=1000.00,
                row_type=RowType.LINE_ITEM,
            ),
            LineItem(
                line_number=2,
                item_name="Widget B",
                description="Standard widget model B",
                unit="PCS",
                quantity=5,
                unit_price=80.00,
                total_price=400.00,
                row_type=RowType.LINE_ITEM,
            ),
        ],
    )


@pytest.fixture
def sample_audit(sample_invoice: Invoice) -> AuditResult:
    """Create sample audit result."""
    return AuditResult(
        id=1,
        invoice_id=1,
        success=True,
        status=AuditStatus.PASS,
        proforma_summary={"total_items": 2, "total_amount": 1500.00},
        bank_details_check={"verified": True, "status": "OK"},
    )


class TestFpdf2ProformaRenderer:
    """Tests for Fpdf2ProformaRenderer."""

    def test_render_returns_bytes(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_invoice: Invoice,
        sample_audit: AuditResult,
    ):
        """Test that render returns bytes."""
        result = renderer.render(sample_invoice, sample_audit)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_render_pdf_header(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_invoice: Invoice,
        sample_audit: AuditResult,
    ):
        """Test that rendered PDF starts with PDF header."""
        result = renderer.render(sample_invoice, sample_audit)
        assert result[:5] == b"%PDF-"

    def test_render_minimal_invoice(
        self,
        renderer: Fpdf2ProformaRenderer,
    ):
        """Test rendering with minimal invoice data."""
        invoice = Invoice(
            id=1,
            invoice_no="MIN-001",
            total_amount=100.0,
            items=[],
        )
        audit = AuditResult(
            invoice_id=1,
            status=AuditStatus.HOLD,
        )
        result = renderer.render(invoice, audit)
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:5] == b"%PDF-"

    def test_render_with_no_bank_details(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_audit: AuditResult,
    ):
        """Test rendering when invoice has no bank details."""
        invoice = Invoice(
            id=1,
            invoice_no="NO-BANK-001",
            total_amount=500.0,
            items=[
                LineItem(
                    item_name="Item",
                    quantity=1,
                    unit_price=500.0,
                    total_price=500.0,
                ),
            ],
        )
        audit = AuditResult(
            invoice_id=1,
            status=AuditStatus.PASS,
        )
        result = renderer.render(invoice, audit)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_render_with_discount(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_audit: AuditResult,
    ):
        """Test rendering with discount amount."""
        invoice = Invoice(
            id=1,
            invoice_no="DISC-001",
            total_amount=900.0,
            subtotal=1000.0,
            discount_amount=100.0,
            items=[],
        )
        result = renderer.render(invoice, sample_audit)
        assert isinstance(result, bytes)
        assert len(result) > 0
