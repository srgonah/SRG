"""
Unit tests for VisionParser JSON validation.

Tests:
- Valid JSON parsing and Pydantic validation
- Invalid JSON handling (syntax errors)
- Missing required fields
- Type coercion for numeric fields
- HS code validation
- Graceful error handling
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.parsers.vision_parser import (
    VisionInvoiceResponse,
    VisionLineItem,
    VisionParser,
)


class TestVisionLineItemValidation:
    """Tests for VisionLineItem Pydantic model."""

    def test_valid_line_item(self):
        """Should accept valid line item data."""
        item = VisionLineItem(
            description="Test Product",
            hs_code="85423100",
            quantity=10,
            unit="PCS",
            unit_price=100.0,
            total_price=1000.0,
        )
        assert item.description == "Test Product"
        assert item.hs_code == "85423100"
        assert item.quantity == 10.0
        assert item.unit_price == 100.0

    def test_coerces_string_numbers(self):
        """Should convert string numbers to float."""
        item = VisionLineItem(
            description="Product",
            quantity="10",
            unit_price="100.50",
            total_price="1005.00",
        )
        assert item.quantity == 10.0
        assert item.unit_price == 100.50
        assert item.total_price == 1005.00

    def test_coerces_numbers_with_commas(self):
        """Should handle numbers with thousand separators."""
        item = VisionLineItem(
            description="Product",
            quantity="1,000",
            unit_price="1,500.50",
            total_price="1,500,500.00",
        )
        assert item.quantity == 1000.0
        assert item.unit_price == 1500.50
        assert item.total_price == 1500500.00

    def test_handles_none_values(self):
        """Should accept None for optional fields."""
        item = VisionLineItem(
            description="Product",
            quantity=None,
            unit_price=None,
        )
        assert item.quantity is None
        assert item.unit_price is None

    def test_handles_null_strings(self):
        """Should convert 'null' strings to None."""
        item = VisionLineItem(
            description="Product",
            quantity="null",
            unit_price="N/A",
        )
        assert item.quantity is None
        assert item.unit_price is None

    def test_validates_hs_code_format(self):
        """Should validate HS code is 6-10 digits."""
        # Valid HS codes
        item = VisionLineItem(description="P", hs_code="854231")
        assert item.hs_code == "854231"

        item = VisionLineItem(description="P", hs_code="8542310000")
        assert item.hs_code == "8542310000"

        # Invalid HS codes should be set to None
        item = VisionLineItem(description="P", hs_code="12345")  # Too short
        assert item.hs_code is None

        item = VisionLineItem(description="P", hs_code="ABC123")  # Non-numeric
        assert item.hs_code is None

    def test_empty_description_coerced_to_string(self):
        """Should handle None description."""
        item = VisionLineItem(description=None)
        assert item.description == ""


class TestVisionInvoiceResponseValidation:
    """Tests for VisionInvoiceResponse Pydantic model."""

    def test_valid_invoice_response(self):
        """Should accept valid invoice data."""
        data = {
            "invoice_no": "INV-001",
            "invoice_date": "2024-01-15",
            "seller_name": "Test Seller",
            "buyer_name": "Test Buyer",
            "currency": "USD",
            "total_amount": 1500.00,
            "items": [
                {
                    "description": "Product A",
                    "quantity": 10,
                    "unit_price": 100.00,
                    "total_price": 1000.00,
                },
                {
                    "description": "Product B",
                    "quantity": 5,
                    "unit_price": 100.00,
                    "total_price": 500.00,
                },
            ],
        }
        invoice = VisionInvoiceResponse.model_validate(data)
        assert invoice.invoice_no == "INV-001"
        assert invoice.total_amount == 1500.00
        assert len(invoice.items) == 2

    def test_defaults_currency_to_usd(self):
        """Should default currency to USD when missing."""
        data = {"items": []}
        invoice = VisionInvoiceResponse.model_validate(data)
        assert invoice.currency == "USD"

    def test_handles_empty_items(self):
        """Should accept empty items list."""
        data = {"invoice_no": "INV-001", "items": []}
        invoice = VisionInvoiceResponse.model_validate(data)
        assert invoice.items == []

    def test_coerces_numeric_totals(self):
        """Should coerce string totals to float."""
        data = {
            "total_amount": "1,500.00",
            "subtotal": "1,200",
            "tax_amount": "300.00",
            "items": [],
        }
        invoice = VisionInvoiceResponse.model_validate(data)
        assert invoice.total_amount == 1500.00
        assert invoice.subtotal == 1200.00
        assert invoice.tax_amount == 300.00


class TestVisionParserJsonExtraction:
    """Tests for VisionParser JSON extraction and validation."""

    @pytest.fixture
    def parser(self):
        return VisionParser()

    def test_extract_json_from_clean_response(self, parser):
        """Should extract JSON from clean response."""
        response = '{"invoice_no": "INV-001", "items": []}'
        json_str = parser._extract_json_string(response)
        assert json_str == response

    def test_extract_json_from_code_block(self, parser):
        """Should extract JSON from markdown code block."""
        response = """Here is the extracted data:

```json
{"invoice_no": "INV-001", "items": []}
```

That's the invoice data."""
        json_str = parser._extract_json_string(response)
        assert json_str.strip() == '{"invoice_no": "INV-001", "items": []}'

    def test_extract_json_with_prose(self, parser):
        """Should extract JSON even with surrounding prose."""
        response = """Based on the image, I extracted:
{"invoice_no": "INV-001", "items": []}
Hope this helps!"""
        json_str = parser._extract_json_string(response)
        assert "invoice_no" in json_str

    def test_parse_valid_json(self, parser):
        """Should parse and validate correct JSON."""
        response = """{
            "invoice_no": "INV-001",
            "invoice_date": "2024-01-15",
            "seller_name": "Test Seller",
            "currency": "USD",
            "total_amount": 1000,
            "items": [
                {"description": "Product", "quantity": 10, "unit_price": 100, "total_price": 1000}
            ]
        }"""
        validated, errors = parser._parse_json_response(response)

        assert validated is not None
        assert len(errors) == 0
        assert validated.invoice_no == "INV-001"
        assert len(validated.items) == 1

    def test_parse_invalid_json_syntax(self, parser):
        """Should return errors for invalid JSON syntax."""
        response = '{"invoice_no": "INV-001", items: []}'  # Missing quotes
        validated, errors = parser._parse_json_response(response)

        assert validated is None
        assert len(errors) > 0
        assert any("Invalid JSON" in e or "syntax" in e.lower() for e in errors)

    def test_parse_no_json_found(self, parser):
        """Should return errors when no JSON found."""
        response = "I couldn't extract any data from the image."
        validated, errors = parser._parse_json_response(response)

        assert validated is None
        assert any("No JSON" in e for e in errors)

    def test_parse_with_invalid_field_types(self, parser):
        """Should handle and coerce invalid field types."""
        response = """{
            "invoice_no": 12345,
            "total_amount": "invalid",
            "items": [
                {"description": "Product", "quantity": "ten"}
            ]
        }"""
        validated, errors = parser._parse_json_response(response)

        # Pydantic should coerce the invoice_no to string
        # and handle invalid numbers gracefully
        if validated:
            assert validated.total_amount is None or validated.total_amount == 0
            assert validated.items[0].quantity is None


class TestVisionParserIntegration:
    """Integration tests for VisionParser (with mocked LLM)."""

    @pytest.fixture
    def parser(self):
        return VisionParser()

    @pytest.mark.asyncio
    async def test_parse_returns_error_without_image(self, parser):
        """Should return error when no image path provided."""
        result = await parser.parse("text", "test.pdf", hints={})

        assert not result.success
        assert "No image path" in result.error

    @pytest.mark.asyncio
    async def test_can_parse_with_ocr_artifacts(self, parser):
        """Should detect OCR artifacts and suggest vision parsing."""
        # Very short text suggests OCR issues
        confidence = parser.can_parse("abc")
        assert confidence > 0

        # High ratio of special characters
        confidence = parser.can_parse("###%%%&&&***!!!")
        assert confidence > 0

    @pytest.mark.asyncio
    async def test_can_parse_with_hints(self, parser):
        """Should respect prefer_vision hint."""
        confidence = parser.can_parse("text", hints={"prefer_vision": True})
        assert confidence >= 0.9

        confidence = parser.can_parse("text", hints={"image_path": "/path/to/image.png"})
        assert confidence >= 0.6

    @pytest.mark.asyncio
    @patch("src.infrastructure.parsers.vision_parser.get_vision_provider")
    @patch("src.infrastructure.parsers.vision_parser.get_settings")
    async def test_parse_with_mocked_llm_success(
        self,
        mock_settings,
        mock_get_provider,
        parser,
    ):
        """Should parse successfully with mocked LLM response."""
        # Mock settings
        settings = MagicMock()
        settings.parser.vision_enabled = True
        settings.parser.vision_min_confidence = 0.6
        mock_settings.return_value = settings

        # Mock vision provider
        mock_provider = AsyncMock()
        mock_response = MagicMock()
        mock_response.error = None
        mock_response.model = "llava:13b"
        mock_response.text = """{
            "invoice_no": "INV-2024-001",
            "invoice_date": "2024-01-15",
            "seller_name": "Test Company",
            "currency": "USD",
            "total_amount": 1500.00,
            "items": [
                {"description": "Widget A", "quantity": 10, "unit_price": 100, "total_price": 1000},
                {"description": "Widget B", "quantity": 5, "unit_price": 100, "total_price": 500}
            ]
        }"""
        mock_provider.analyze_image.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        result = await parser.parse(
            "text",
            "test.pdf",
            hints={"image_path": "/path/to/image.png"},
        )

        assert result.success
        assert result.invoice.invoice_no == "INV-2024-001"
        assert len(result.items) == 2
        assert result.confidence > 0

    @pytest.mark.asyncio
    @patch("src.infrastructure.parsers.vision_parser.get_vision_provider")
    @patch("src.infrastructure.parsers.vision_parser.get_settings")
    async def test_parse_with_mocked_llm_invalid_json(
        self,
        mock_settings,
        mock_get_provider,
        parser,
    ):
        """Should handle invalid JSON from LLM gracefully."""
        # Mock settings
        settings = MagicMock()
        settings.parser.vision_enabled = True
        mock_settings.return_value = settings

        # Mock vision provider with invalid response
        mock_provider = AsyncMock()
        mock_response = MagicMock()
        mock_response.error = None
        mock_response.model = "llava:13b"
        mock_response.text = "I'm sorry, I couldn't read the invoice clearly."
        mock_provider.analyze_image.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        result = await parser.parse(
            "text",
            "test.pdf",
            hints={"image_path": "/path/to/image.png"},
        )

        assert not result.success
        assert "validation_errors" in result.metadata or "JSON" in result.error

    @pytest.mark.asyncio
    @patch("src.infrastructure.parsers.vision_parser.get_settings")
    async def test_parse_when_vision_disabled(self, mock_settings, parser):
        """Should return error when vision is disabled."""
        settings = MagicMock()
        settings.parser.vision_enabled = False
        mock_settings.return_value = settings

        result = await parser.parse(
            "text",
            "test.pdf",
            hints={"image_path": "/path/to/image.png"},
        )

        assert not result.success
        assert "disabled" in result.error.lower()


class TestConfidenceCalculation:
    """Tests for confidence score calculation."""

    @pytest.fixture
    def parser(self):
        return VisionParser()

    def test_full_confidence_with_complete_data(self, parser):
        """Should return high confidence with complete data."""
        from src.core.entities import Invoice, LineItem

        invoice = Invoice(
            invoice_no="INV-001",
            invoice_date="2024-01-15",
            seller_name="Test Seller",
            total_amount=1000.0,
        )
        items = [
            LineItem(
                line_number=1,
                item_name="Product",
                quantity=10,
                unit_price=100,
                total_price=1000,
            )
        ]

        confidence = parser._calculate_extraction_confidence(invoice, items)
        assert confidence >= 0.8

    def test_low_confidence_with_minimal_data(self, parser):
        """Should return low confidence with minimal data."""
        from src.core.entities import Invoice

        invoice = Invoice()  # Empty invoice
        items = []

        confidence = parser._calculate_extraction_confidence(invoice, items)
        assert confidence < 0.3

    def test_medium_confidence_with_partial_data(self, parser):
        """Should return medium confidence with partial data."""
        from src.core.entities import Invoice, LineItem

        invoice = Invoice(invoice_no="INV-001")
        items = [
            LineItem(line_number=1, item_name="Product", quantity=10)
            # Missing prices
        ]

        confidence = parser._calculate_extraction_confidence(invoice, items)
        assert 0.2 <= confidence <= 0.6
