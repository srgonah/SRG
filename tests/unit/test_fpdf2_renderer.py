"""Tests for PDF renderers (proforma and sales)."""

import zlib

import pytest

from src.config.settings import PdfSettings
from src.core.entities.invoice import (
    AuditResult,
    AuditStatus,
    BankDetails,
    Invoice,
    LineItem,
    RowType,
)
from src.core.entities.local_sale import LocalSalesInvoice, LocalSalesItem
from src.infrastructure.pdf.fpdf2_renderer import Fpdf2ProformaRenderer, _contains_arabic
from src.infrastructure.pdf.sales_pdf_renderer import Fpdf2SalesRenderer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Decompress FlateDecode streams in *pdf_bytes* and return all text.

    fpdf2 compresses page content with zlib (FlateDecode).  We find
    each ``stream ... endstream`` block, attempt to decompress it, and
    concatenate the decoded text.  This is a simplistic extraction
    used only for testing purposes.
    """
    texts: list[str] = []
    # Also search the uncompressed portion of the PDF (object metadata)
    try:
        texts.append(pdf_bytes.decode("latin-1"))
    except Exception:
        pass

    # Extract compressed streams
    start_marker = b"stream\n"
    end_marker = b"\nendstream"
    idx = 0
    while True:
        s = pdf_bytes.find(start_marker, idx)
        if s == -1:
            break
        s += len(start_marker)
        e = pdf_bytes.find(end_marker, s)
        if e == -1:
            break
        raw = pdf_bytes[s:e]
        try:
            decompressed = zlib.decompress(raw)
            texts.append(decompressed.decode("latin-1", errors="replace"))
        except Exception:
            pass
        idx = e + len(end_marker)

    return "\n".join(texts)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_pdf_settings() -> PdfSettings:
    """Default PdfSettings for testing."""
    return PdfSettings(
        company_name="Test Corp",
        company_address="123 Test Street",
        company_phone="+1-555-0100",
        company_email="info@testcorp.com",
        footer_text="Test Footer",
        logo_path="",
        arabic_font_path="",
    )


@pytest.fixture
def renderer(default_pdf_settings: PdfSettings) -> Fpdf2ProformaRenderer:
    """Create proforma renderer instance with test settings."""
    return Fpdf2ProformaRenderer(pdf_settings=default_pdf_settings)


@pytest.fixture
def sales_renderer(default_pdf_settings: PdfSettings) -> Fpdf2SalesRenderer:
    """Create sales renderer instance with test settings."""
    return Fpdf2SalesRenderer(pdf_settings=default_pdf_settings)


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


@pytest.fixture
def sample_sales_invoice() -> LocalSalesInvoice:
    """Create sample sales invoice for PDF generation."""
    return LocalSalesInvoice(
        id=1,
        invoice_number="SALE-2026-001",
        customer_name="Test Customer",
        sale_date="2026-01-15",
        notes="Test sale notes",
        items=[
            LocalSalesItem(
                id=1,
                inventory_item_id=10,
                material_id="MAT-001",
                description="Widget A",
                quantity=3,
                unit_price=150.00,
                cost_basis=300.00,
            ),
            LocalSalesItem(
                id=2,
                inventory_item_id=11,
                material_id="MAT-002",
                description="Widget B",
                quantity=2,
                unit_price=200.00,
                cost_basis=250.00,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Proforma renderer tests
# ---------------------------------------------------------------------------


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

    def test_render_contains_invoice_number(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_invoice: Invoice,
        sample_audit: AuditResult,
    ):
        """Test that PDF content contains the invoice number."""
        result = renderer.render(sample_invoice, sample_audit)
        text = _extract_pdf_text(result)
        assert "INV-2026-001" in text

    def test_render_contains_proforma_title(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_invoice: Invoice,
        sample_audit: AuditResult,
    ):
        """Test that PDF contains PROFORMA INVOICE title."""
        result = renderer.render(sample_invoice, sample_audit)
        text = _extract_pdf_text(result)
        assert "PROFORMA INVOICE" in text

    def test_render_contains_item_names(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_invoice: Invoice,
        sample_audit: AuditResult,
    ):
        """Test that PDF contains item descriptions."""
        result = renderer.render(sample_invoice, sample_audit)
        text = _extract_pdf_text(result)
        assert "Premium widget model A" in text
        assert "Standard widget model B" in text

    def test_render_contains_totals(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_invoice: Invoice,
        sample_audit: AuditResult,
    ):
        """Test that PDF contains total amount."""
        result = renderer.render(sample_invoice, sample_audit)
        text = _extract_pdf_text(result)
        assert "1,500.00" in text

    def test_render_contains_page_number(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_invoice: Invoice,
        sample_audit: AuditResult,
    ):
        """Test that PDF footer contains page numbering."""
        result = renderer.render(sample_invoice, sample_audit)
        text = _extract_pdf_text(result)
        assert "Page" in text

    def test_render_contains_footer_text(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_invoice: Invoice,
        sample_audit: AuditResult,
    ):
        """Test that PDF footer contains configurable footer text."""
        result = renderer.render(sample_invoice, sample_audit)
        text = _extract_pdf_text(result)
        assert "Test Footer" in text

    def test_render_contains_company_name(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_invoice: Invoice,
        sample_audit: AuditResult,
    ):
        """Test that PDF contains company name from settings."""
        result = renderer.render(sample_invoice, sample_audit)
        text = _extract_pdf_text(result)
        assert "Test Corp" in text

    def test_render_logo_placeholder_produces_nonempty_pdf(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_invoice: Invoice,
        sample_audit: AuditResult,
    ):
        """Test that logo placeholder area exists (PDF is non-empty)."""
        result = renderer.render(sample_invoice, sample_audit)
        assert len(result) > 500  # A reasonable minimum PDF size
        text = _extract_pdf_text(result)
        assert "LOGO" in text

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

    def test_custom_settings_reflected_in_output(self):
        """Test that custom PdfSettings are reflected in rendered PDF."""
        custom_settings = PdfSettings(
            company_name="My Custom Company",
            footer_text="Custom Footer Line",
        )
        r = Fpdf2ProformaRenderer(pdf_settings=custom_settings)
        invoice = Invoice(id=1, invoice_no="CUST-001", total_amount=100.0)
        audit = AuditResult(invoice_id=1, status=AuditStatus.PASS)
        result = r.render(invoice, audit)
        text = _extract_pdf_text(result)
        assert "My Custom Company" in text
        assert "Custom Footer Line" in text

    def test_arabic_text_does_not_crash(
        self,
        renderer: Fpdf2ProformaRenderer,
    ):
        """Test that Arabic text in fields does not crash the renderer.

        Without an Arabic font file loaded, Arabic glyphs will not
        render correctly but the renderer should not raise.
        """
        invoice = Invoice(
            id=1,
            invoice_no="AR-001",
            seller_name="\u0634\u0631\u0643\u0629 \u0627\u062e\u062a\u0628\u0627\u0631",
            buyer_name="\u0639\u0645\u064a\u0644 \u0627\u062e\u062a\u0628\u0627\u0631",
            total_amount=500.0,
            items=[
                LineItem(
                    item_name="\u0645\u0646\u062a\u062c",
                    description="\u0645\u0646\u062a\u062c \u0627\u062e\u062a\u0628\u0627\u0631",
                    quantity=1,
                    unit_price=500.0,
                    total_price=500.0,
                ),
            ],
        )
        audit = AuditResult(invoice_id=1, status=AuditStatus.PASS)
        # Should not raise
        result = renderer.render(invoice, audit)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_audit_status_in_pdf(
        self,
        renderer: Fpdf2ProformaRenderer,
        sample_invoice: Invoice,
    ):
        """Test that audit status value appears in the PDF."""
        audit = AuditResult(invoice_id=1, status=AuditStatus.FAIL)
        result = renderer.render(sample_invoice, audit)
        text = _extract_pdf_text(result)
        assert "FAIL" in text


# ---------------------------------------------------------------------------
# Sales renderer tests
# ---------------------------------------------------------------------------


class TestFpdf2SalesRenderer:
    """Tests for Fpdf2SalesRenderer."""

    def test_render_returns_bytes(
        self,
        sales_renderer: Fpdf2SalesRenderer,
        sample_sales_invoice: LocalSalesInvoice,
    ):
        """Test that render returns bytes."""
        result = sales_renderer.render(sample_sales_invoice)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_render_pdf_header(
        self,
        sales_renderer: Fpdf2SalesRenderer,
        sample_sales_invoice: LocalSalesInvoice,
    ):
        """Test that rendered PDF starts with PDF header."""
        result = sales_renderer.render(sample_sales_invoice)
        assert result[:5] == b"%PDF-"

    def test_render_contains_sales_title(
        self,
        sales_renderer: Fpdf2SalesRenderer,
        sample_sales_invoice: LocalSalesInvoice,
    ):
        """Test that PDF contains SALES INVOICE title."""
        result = sales_renderer.render(sample_sales_invoice)
        text = _extract_pdf_text(result)
        assert "SALES INVOICE" in text

    def test_render_contains_invoice_number(
        self,
        sales_renderer: Fpdf2SalesRenderer,
        sample_sales_invoice: LocalSalesInvoice,
    ):
        """Test that PDF contains the invoice number."""
        result = sales_renderer.render(sample_sales_invoice)
        text = _extract_pdf_text(result)
        assert "SALE-2026-001" in text

    def test_render_contains_customer_name(
        self,
        sales_renderer: Fpdf2SalesRenderer,
        sample_sales_invoice: LocalSalesInvoice,
    ):
        """Test that PDF contains customer name."""
        result = sales_renderer.render(sample_sales_invoice)
        text = _extract_pdf_text(result)
        assert "Test Customer" in text

    def test_render_contains_item_descriptions(
        self,
        sales_renderer: Fpdf2SalesRenderer,
        sample_sales_invoice: LocalSalesInvoice,
    ):
        """Test that PDF contains item descriptions."""
        result = sales_renderer.render(sample_sales_invoice)
        text = _extract_pdf_text(result)
        assert "Widget A" in text
        assert "Widget B" in text

    def test_render_contains_page_number(
        self,
        sales_renderer: Fpdf2SalesRenderer,
        sample_sales_invoice: LocalSalesInvoice,
    ):
        """Test that sales PDF footer contains page numbering."""
        result = sales_renderer.render(sample_sales_invoice)
        text = _extract_pdf_text(result)
        assert "Page" in text

    def test_render_contains_footer_text(
        self,
        sales_renderer: Fpdf2SalesRenderer,
        sample_sales_invoice: LocalSalesInvoice,
    ):
        """Test that sales PDF footer contains configurable text."""
        result = sales_renderer.render(sample_sales_invoice)
        text = _extract_pdf_text(result)
        assert "Test Footer" in text

    def test_render_contains_summary(
        self,
        sales_renderer: Fpdf2SalesRenderer,
        sample_sales_invoice: LocalSalesInvoice,
    ):
        """Test that PDF contains summary section."""
        result = sales_renderer.render(sample_sales_invoice)
        text = _extract_pdf_text(result)
        assert "Summary" in text
        assert "Grand Total" in text

    def test_render_contains_company_name(
        self,
        sales_renderer: Fpdf2SalesRenderer,
        sample_sales_invoice: LocalSalesInvoice,
    ):
        """Test that PDF contains company name from settings."""
        result = sales_renderer.render(sample_sales_invoice)
        text = _extract_pdf_text(result)
        assert "Test Corp" in text

    def test_render_logo_placeholder(
        self,
        sales_renderer: Fpdf2SalesRenderer,
        sample_sales_invoice: LocalSalesInvoice,
    ):
        """Test that logo placeholder area exists in sales PDF."""
        result = sales_renderer.render(sample_sales_invoice)
        assert len(result) > 500
        text = _extract_pdf_text(result)
        assert "LOGO" in text

    def test_arabic_text_does_not_crash(
        self,
        sales_renderer: Fpdf2SalesRenderer,
    ):
        """Test that Arabic text in sales invoice does not crash."""
        invoice = LocalSalesInvoice(
            id=1,
            invoice_number="SALE-AR-001",
            customer_name="\u0639\u0645\u064a\u0644 \u0627\u062e\u062a\u0628\u0627\u0631",
            items=[
                LocalSalesItem(
                    id=1,
                    inventory_item_id=1,
                    material_id="MAT-001",
                    description="\u0645\u0646\u062a\u062c \u0627\u062e\u062a\u0628\u0627\u0631",
                    quantity=1,
                    unit_price=100.0,
                    cost_basis=50.0,
                ),
            ],
        )
        result = sales_renderer.render(invoice)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_render_empty_items(
        self,
        sales_renderer: Fpdf2SalesRenderer,
    ):
        """Test rendering a sales invoice with no items."""
        invoice = LocalSalesInvoice(
            id=1,
            invoice_number="SALE-EMPTY-001",
            customer_name="No Items Customer",
            items=[],
        )
        result = sales_renderer.render(invoice)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# Arabic detection helper tests
# ---------------------------------------------------------------------------


class TestArabicDetection:
    """Tests for the Arabic text detection helper."""

    def test_detects_arabic_text(self):
        assert _contains_arabic("\u0634\u0631\u0643\u0629")

    def test_does_not_detect_latin_text(self):
        assert not _contains_arabic("Hello World")

    def test_detects_mixed_text(self):
        assert _contains_arabic("Hello \u0645\u0631\u062d\u0628\u0627")

    def test_empty_string(self):
        assert not _contains_arabic("")
