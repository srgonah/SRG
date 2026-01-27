"""Unit tests for parser interface dataclasses."""

import pytest

from src.core.entities.invoice import Invoice, LineItem
from src.core.interfaces.parser import (
    IInvoiceParser,
    IParserRegistry,
    ITemplateDetector,
    ITextExtractor,
    ParserResult,
    TemplateMatch,
)


class TestParserResult:
    """Tests for ParserResult dataclass."""

    def test_minimal_initialization(self):
        result = ParserResult(success=True)
        assert result.success is True
        assert result.invoice is None
        assert result.items == []
        assert result.confidence == 0.0
        assert result.parser_name == ""
        assert result.error is None
        assert result.metadata == {}

    def test_successful_result(self):
        invoice = Invoice(invoice_no="INV-001")
        items = [LineItem(item_name="Product A")]
        result = ParserResult(
            success=True,
            invoice=invoice,
            items=items,
            confidence=0.95,
            parser_name="table_aware",
        )
        assert result.success is True
        assert result.invoice.invoice_no == "INV-001"
        assert len(result.items) == 1
        assert result.confidence == 0.95
        assert result.parser_name == "table_aware"

    def test_failed_result(self):
        result = ParserResult(
            success=False,
            error="No tables found in document",
            parser_name="table_aware",
        )
        assert result.success is False
        assert result.error == "No tables found in document"

    def test_items_default_empty_list(self):
        """Verify items defaults to empty list, not None."""
        result = ParserResult(success=True)
        assert result.items is not None
        assert result.items == []
        # Verify it's mutable
        result.items.append(LineItem(item_name="Test"))
        assert len(result.items) == 1

    def test_metadata_default_empty_dict(self):
        """Verify metadata defaults to empty dict, not None."""
        result = ParserResult(success=True)
        assert result.metadata is not None
        assert result.metadata == {}
        # Verify it's mutable
        result.metadata["key"] = "value"
        assert result.metadata["key"] == "value"

    def test_with_metadata(self):
        result = ParserResult(
            success=True,
            metadata={
                "pages_processed": 3,
                "tables_found": 2,
                "processing_time": 1.5,
            },
        )
        assert result.metadata["pages_processed"] == 3
        assert result.metadata["tables_found"] == 2


class TestTemplateMatch:
    """Tests for TemplateMatch dataclass."""

    def test_required_fields(self):
        match = TemplateMatch(
            template_id="tpl_001",
            template_name="Company A Invoice",
            confidence=0.92,
            company_key="COMPANY_A",
        )
        assert match.template_id == "tpl_001"
        assert match.template_name == "Company A Invoice"
        assert match.confidence == 0.92
        assert match.company_key == "COMPANY_A"

    def test_default_parser_hints(self):
        match = TemplateMatch(
            template_id="tpl_001",
            template_name="Test",
            confidence=0.9,
            company_key="TEST",
        )
        assert match.parser_hints is not None
        assert match.parser_hints == {}

    def test_with_parser_hints(self):
        match = TemplateMatch(
            template_id="tpl_001",
            template_name="Test Template",
            confidence=0.95,
            company_key="TEST_CO",
            parser_hints={
                "table_start_row": 5,
                "columns": ["item", "qty", "price", "total"],
                "date_format": "DD/MM/YYYY",
            },
        )
        assert match.parser_hints["table_start_row"] == 5
        assert "qty" in match.parser_hints["columns"]
        assert match.parser_hints["date_format"] == "DD/MM/YYYY"

    def test_parser_hints_mutability(self):
        """Verify parser_hints can be modified."""
        match = TemplateMatch(
            template_id="tpl_001",
            template_name="Test",
            confidence=0.9,
            company_key="TEST",
        )
        match.parser_hints["new_key"] = "new_value"
        assert match.parser_hints["new_key"] == "new_value"


class TestIInvoiceParserInterface:
    """Tests for IInvoiceParser abstract interface."""

    def test_is_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IInvoiceParser()

    def test_abstract_methods_and_properties(self):
        """Verify all required abstract methods/properties are defined."""
        # Note: 'name' and 'priority' are abstract properties
        abstract_methods = {"name", "priority", "parse", "can_parse"}
        actual_methods = set(IInvoiceParser.__abstractmethods__)
        assert abstract_methods == actual_methods


class TestITemplateDetectorInterface:
    """Tests for ITemplateDetector abstract interface."""

    def test_is_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ITemplateDetector()

    def test_abstract_methods_defined(self):
        abstract_methods = {
            "detect",
            "load_templates",
            "get_template",
            "list_templates",
        }
        actual_methods = set(ITemplateDetector.__abstractmethods__)
        assert abstract_methods == actual_methods


class TestITextExtractorInterface:
    """Tests for ITextExtractor abstract interface."""

    def test_is_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ITextExtractor()

    def test_abstract_methods_defined(self):
        abstract_methods = {
            "extract",
            "extract_pages",
            "extract_with_images",
        }
        actual_methods = set(ITextExtractor.__abstractmethods__)
        assert abstract_methods == actual_methods


class TestIParserRegistryInterface:
    """Tests for IParserRegistry abstract interface."""

    def test_is_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IParserRegistry()

    def test_abstract_methods_defined(self):
        abstract_methods = {
            "register",
            "unregister",
            "get_parsers",
            "parse",
            "parse_with_parser",
        }
        actual_methods = set(IParserRegistry.__abstractmethods__)
        assert abstract_methods == actual_methods
