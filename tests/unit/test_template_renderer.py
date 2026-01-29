"""Tests for TemplateRenderer PDF generation."""

import zlib

import pytest

from src.core.entities.template import (
    PdfTemplate,
    Position,
    TemplatePositions,
    TemplateType,
)
from src.infrastructure.pdf.template_renderer import TemplateRenderer


def _extract_pdf_text(pdf_bytes: bytes | bytearray) -> str:
    """Extract text from PDF bytes for testing.

    Decompresses FlateDecode streams and concatenates text.
    This is a simplistic extraction for testing purposes.
    """
    # Convert bytearray to bytes if needed
    if isinstance(pdf_bytes, bytearray):
        pdf_bytes = bytes(pdf_bytes)

    texts: list[str] = []

    # Also search the uncompressed portion
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


@pytest.fixture
def proforma_template() -> PdfTemplate:
    """Create a proforma template for testing."""
    return PdfTemplate(
        id=1,
        name="Test Proforma",
        description="Test proforma template",
        template_type=TemplateType.PROFORMA,
        page_size="A4",
        orientation="portrait",
        margin_top=15.0,
        margin_bottom=15.0,
        margin_left=10.0,
        margin_right=10.0,
        is_default=True,
        is_active=True,
    )


@pytest.fixture
def sales_template() -> PdfTemplate:
    """Create a sales template for testing."""
    return PdfTemplate(
        id=2,
        name="Test Sales",
        description="Test sales template",
        template_type=TemplateType.SALES,
        page_size="A4",
        orientation="portrait",
        is_default=True,
        is_active=True,
    )


@pytest.fixture
def sample_proforma_data() -> dict:
    """Sample data for proforma invoice generation."""
    return {
        "document_type": "proforma",
        "document_number": "PRO-2026-001",
        "document_date": "2026-01-15",
        "valid_until": "2026-02-15",
        "currency": "USD",
        "seller": {
            "name": "Test Seller Corp",
            "address": "123 Seller Street\nCity, Country",
            "phone": "+1-555-0100",
            "email": "seller@test.com",
            "tax_id": "TAX123456",
        },
        "buyer": {
            "name": "Test Buyer Inc",
            "address": "456 Buyer Avenue\nTown, Country",
            "phone": "+1-555-0200",
            "email": "buyer@test.com",
            "tax_id": "TAX789012",
        },
        "bank_details": {
            "bank_name": "First National Bank",
            "account_name": "Test Seller Corp",
            "account_number": "1234567890",
            "iban": "US12 3456 7890 1234 5678",
            "swift_code": "FNBKUS12",
        },
        "items": [
            {
                "description": "Widget Alpha",
                "quantity": 10,
                "unit": "pcs",
                "unit_price": 25.00,
                "total": 250.00,
            },
            {
                "description": "Widget Beta",
                "quantity": 5,
                "unit": "pcs",
                "unit_price": 50.00,
                "total": 250.00,
            },
        ],
        "subtotal": 500.00,
        "tax_amount": 50.00,
        "total_amount": 550.00,
        "notes": "Thank you for your business!",
        "terms": "Payment due within 30 days.",
        "payment_terms": "50% advance, 50% upon delivery",
    }


@pytest.fixture
def sample_sales_data() -> dict:
    """Sample data for sales invoice generation."""
    return {
        "document_type": "sales_invoice",
        "document_number": "INV-2026-001",
        "document_date": "2026-01-15",
        "currency": "AED",
        "seller": {
            "name": "Our Company LLC",
            "address": "Business Bay, Dubai",
            "phone": "+971-4-123-4567",
            "email": "info@ourcompany.ae",
        },
        "buyer": {
            "name": "Customer Corp",
            "address": "Al Quoz, Dubai",
            "phone": "+971-4-765-4321",
            "email": "purchase@customer.ae",
        },
        "items": [
            {
                "description": "Product A",
                "quantity": 3,
                "unit": "pcs",
                "unit_price": 100.00,
                "total": 300.00,
            },
        ],
        "subtotal": 300.00,
        "tax_amount": 15.00,
        "total_amount": 315.00,
    }


class TestTemplateRenderer:
    """Tests for TemplateRenderer."""

    def test_render_returns_bytes(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that render returns bytes or bytearray."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)

        assert isinstance(result, (bytes, bytearray))
        assert len(result) > 0

    def test_render_pdf_header(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that rendered PDF starts with PDF header."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)

        assert bytes(result[:5]) == b"%PDF-"

    def test_render_without_template(self, sample_proforma_data: dict):
        """Test rendering without a template (uses defaults)."""
        renderer = TemplateRenderer(None)
        result = renderer.render(sample_proforma_data)

        assert isinstance(result, (bytes, bytearray))
        assert bytes(result[:5]) == b"%PDF-"

    def test_render_contains_document_number(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains document number."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "PRO-2026-001" in text

    def test_render_contains_proforma_title(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains PROFORMA INVOICE title."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "PROFORMA INVOICE" in text

    def test_render_contains_sales_title(
        self, sales_template: PdfTemplate, sample_sales_data: dict
    ):
        """Test that sales PDF contains SALES INVOICE title."""
        renderer = TemplateRenderer(sales_template)
        result = renderer.render(sample_sales_data)
        text = _extract_pdf_text(result)

        assert "SALES INVOICE" in text

    def test_render_contains_seller_info(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains seller information."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "Test Seller Corp" in text

    def test_render_contains_buyer_info(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains buyer information."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "Test Buyer Inc" in text
        assert "Bill To" in text

    def test_render_contains_items(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains item descriptions."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "Widget Alpha" in text
        assert "Widget Beta" in text

    def test_render_contains_totals(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains total amount."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "550.00" in text
        assert "TOTAL" in text

    def test_render_contains_bank_details(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains bank details when provided."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "First National Bank" in text
        assert "Bank Details" in text

    def test_render_without_bank_details(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF renders without bank details."""
        data = sample_proforma_data.copy()
        del data["bank_details"]

        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(data)

        assert isinstance(result, (bytes, bytearray))
        assert bytes(result[:5]) == b"%PDF-"

    def test_render_contains_page_number(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains page numbering."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "Page" in text

    def test_render_contains_notes(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains notes when provided."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "Thank you for your business" in text
        assert "Notes" in text

    def test_render_contains_terms(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains terms when provided."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "Payment due within 30 days" in text

    def test_render_contains_payment_terms(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains payment terms when provided."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "50% advance" in text

    def test_render_minimal_data(self, proforma_template: PdfTemplate):
        """Test rendering with minimal data."""
        minimal_data = {
            "document_type": "proforma",
            "document_number": "MIN-001",
            "document_date": "2026-01-01",
            "items": [],
        }

        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(minimal_data)

        assert isinstance(result, (bytes, bytearray))
        assert bytes(result[:5]) == b"%PDF-"

    def test_render_generic_document(self, proforma_template: PdfTemplate):
        """Test rendering a generic document type."""
        data = {
            "document_type": "custom",
            "content": "This is a test document",
        }

        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(data)

        assert isinstance(result, (bytes, bytearray))
        assert bytes(result[:5]) == b"%PDF-"

    def test_render_with_valid_until(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF contains valid until date for proforma."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "Valid Until" in text
        assert "2026-02-15" in text

    def test_render_with_tax(
        self, proforma_template: PdfTemplate, sample_proforma_data: dict
    ):
        """Test that PDF shows tax amount when provided."""
        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(sample_proforma_data)
        text = _extract_pdf_text(result)

        assert "Tax" in text
        assert "50.00" in text

    def test_render_with_discount(self, proforma_template: PdfTemplate):
        """Test that PDF shows discount when provided."""
        data = {
            "document_type": "proforma",
            "document_number": "DISC-001",
            "document_date": "2026-01-01",
            "items": [],
            "subtotal": 100.00,
            "discount_amount": 10.00,
            "total_amount": 90.00,
        }

        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(data)
        text = _extract_pdf_text(result)

        assert "Discount" in text

    def test_render_quote_document(self, proforma_template: PdfTemplate):
        """Test rendering a quote document."""
        data = {
            "document_type": "quote",
            "document_number": "QUO-001",
            "document_date": "2026-01-01",
            "items": [],
        }

        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(data)
        text = _extract_pdf_text(result)

        assert "QUOTATION" in text

    def test_render_receipt_document(self, proforma_template: PdfTemplate):
        """Test rendering a receipt document."""
        data = {
            "document_type": "receipt",
            "document_number": "REC-001",
            "document_date": "2026-01-01",
            "items": [],
        }

        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(data)
        text = _extract_pdf_text(result)

        assert "RECEIPT" in text

    def test_render_large_item_list(self, proforma_template: PdfTemplate):
        """Test rendering with many items (multi-page scenario)."""
        items = [
            {
                "description": f"Item {i}",
                "quantity": 1,
                "unit": "pcs",
                "unit_price": 10.00,
                "total": 10.00,
            }
            for i in range(50)
        ]

        data = {
            "document_type": "proforma",
            "document_number": "LARGE-001",
            "document_date": "2026-01-01",
            "items": items,
            "subtotal": 500.00,
            "total_amount": 500.00,
        }

        renderer = TemplateRenderer(proforma_template)
        result = renderer.render(data)

        assert isinstance(result, (bytes, bytearray))
        assert bytes(result[:5]) == b"%PDF-"
        # Should be larger due to more content
        assert len(result) > 4500


class TestTemplateRendererWithPositions:
    """Tests for TemplateRenderer with custom positions."""

    def test_render_with_custom_positions(self, sample_proforma_data: dict):
        """Test rendering with custom element positions."""
        template = PdfTemplate(
            id=1,
            name="Custom Positions",
            template_type=TemplateType.PROFORMA,
            positions=TemplatePositions(
                company_name=Position(x=50, y=20, font_size=16),
                signature=Position(x=30, y=260, width=50, height=25),
            ),
            is_active=True,
        )

        renderer = TemplateRenderer(template)
        result = renderer.render(sample_proforma_data)

        assert isinstance(result, (bytes, bytearray))
        assert bytes(result[:5]) == b"%PDF-"

    def test_render_landscape_orientation(self, sample_proforma_data: dict):
        """Test rendering with landscape orientation."""
        template = PdfTemplate(
            id=1,
            name="Landscape Template",
            template_type=TemplateType.PROFORMA,
            orientation="landscape",
            is_active=True,
        )

        renderer = TemplateRenderer(template)
        result = renderer.render(sample_proforma_data)

        assert isinstance(result, (bytes, bytearray))
        assert bytes(result[:5]) == b"%PDF-"
