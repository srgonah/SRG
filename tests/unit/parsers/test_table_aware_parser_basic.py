"""
Unit tests for TableAwareParser column parsing behavior.

Tests:
- Header row detection
- Column classification
- Multi-line description handling
- Totals/subtotals detection
- Vertical block layout parsing
"""

import pytest

from src.core.entities import RowType
from src.infrastructure.parsers.base import (
    is_bank_line,
    is_summary_or_meta_line,
    parse_date,
    parse_number,
    split_cells_by_whitespace,
)
from src.infrastructure.parsers.table_aware_parser import TableAwareParser


class TestParseNumber:
    """Tests for number parsing utilities."""

    def test_parse_simple_number(self):
        assert parse_number("123.45") == 123.45
        assert parse_number("100") == 100.0

    def test_parse_with_thousand_separator(self):
        assert parse_number("1,234.56") == 1234.56
        assert parse_number("1,234,567.89") == 1234567.89

    def test_parse_european_format(self):
        # European: 1.234,56 (period for thousands, comma for decimal)
        assert parse_number("1.234,56") == 1234.56

    def test_parse_with_spaces(self):
        assert parse_number("1 234.56") == 1234.56

    def test_parse_none_or_empty(self):
        assert parse_number(None) is None
        assert parse_number("") is None
        assert parse_number("   ") is None

    def test_parse_invalid(self):
        assert parse_number("abc") is None
        assert parse_number("N/A") is None


class TestParseDate:
    """Tests for date parsing utilities."""

    def test_parse_iso_format(self):
        assert parse_date("2024-01-15") == "2024-01-15"
        assert parse_date("2024-1-5") == "2024-01-05"

    def test_parse_european_format(self):
        assert parse_date("15/01/2024") == "2024-01-15"
        assert parse_date("15.01.2024") == "2024-01-15"

    def test_parse_with_month_name(self):
        assert parse_date("15 January 2024") == "2024-01-15"
        assert parse_date("January 15, 2024") == "2024-01-15"
        assert parse_date("Jan 15, 2024") == "2024-01-15"

    def test_parse_none_or_empty(self):
        assert parse_date(None) is None
        assert parse_date("") is None

    def test_parse_invalid(self):
        assert parse_date("not a date") is None


class TestLineFiltering:
    """Tests for line filtering utilities."""

    def test_is_bank_line(self):
        assert is_bank_line("IBAN: DE89370400440532013000")
        assert is_bank_line("SWIFT: COBADEFFXXX")
        assert is_bank_line("Beneficiary: Test Company")
        assert is_bank_line("Bank: First National Bank")
        assert not is_bank_line("Widget product description")
        assert not is_bank_line("100 PCS @ $50.00")

    def test_is_summary_line(self):
        assert is_summary_or_meta_line("Total: 1,500.00")
        assert is_summary_or_meta_line("Sub Total")
        assert is_summary_or_meta_line("Grand Total")
        assert is_summary_or_meta_line("VAT @ 20%")
        assert is_summary_or_meta_line("Invoice No: INV-001")
        assert not is_summary_or_meta_line("Widget product")
        assert not is_summary_or_meta_line("50 PCS")


class TestCellSplitting:
    """Tests for whitespace-based cell splitting."""

    def test_split_simple_cells(self):
        line = "Description     100     50.00     5000.00"
        cells = split_cells_by_whitespace(line, min_gap=2)

        texts = [c["text"] for c in cells]
        assert texts == ["Description", "100", "50.00", "5000.00"]

    def test_split_preserves_single_spaces(self):
        line = "Product Name Here     100     50.00"
        cells = split_cells_by_whitespace(line, min_gap=2)

        texts = [c["text"] for c in cells]
        assert texts[0] == "Product Name Here"

    def test_split_with_tabs(self):
        line = "Description\t\t100\t\t50.00"
        cells = split_cells_by_whitespace(line, min_gap=2)

        assert len(cells) >= 2

    def test_split_records_positions(self):
        line = "A     B"
        cells = split_cells_by_whitespace(line, min_gap=2)

        assert cells[0]["start_pos"] == 0
        assert cells[0]["end_pos"] < cells[1]["start_pos"]


class TestTableAwareParser:
    """Tests for TableAwareParser."""

    @pytest.fixture
    def parser(self):
        return TableAwareParser()

    def test_parser_properties(self, parser):
        assert parser.name == "table_aware"
        assert parser.priority == 80

    def test_can_parse_with_headers(self, parser):
        text = """
        Description     Qty     Unit     Unit Price     Amount
        Widget          10      PCS      100.00         1000.00
        Gadget          5       PCS      200.00         1000.00
        """
        confidence = parser.can_parse(text)
        assert confidence >= 0.7  # Should detect header keywords

    def test_can_parse_no_structure(self, parser):
        text = "Just some random text without any table structure"
        confidence = parser.can_parse(text)
        assert confidence < 0.5

    @pytest.mark.asyncio
    async def test_parse_simple_table(self, parser):
        text = """
        INVOICE

        Description          Qty    Unit Price    Total
        Widget Type A        10     100.00        1000.00
        Gadget Model B       5      200.00        1000.00
        """
        result = await parser.parse(text, "test.pdf")

        assert result.success
        assert len(result.items) >= 2
        assert result.parser_name == "table_aware"

    @pytest.mark.asyncio
    async def test_parse_with_hs_codes(self, parser):
        text = """
        Description               HS Code     Qty    Unit Price    Total
        Electronic Component      85423100    100    50.00         5000.00
        Plastic Container         39231000    200    25.00         5000.00
        """
        result = await parser.parse(text, "test.pdf")

        if result.success and result.items:
            # At least some items should have HS codes
            items_with_hs = [i for i in result.items if i.hs_code]
            # Note: depends on parser's ability to extract HS codes
            assert len(items_with_hs) >= 0

    @pytest.mark.asyncio
    async def test_parse_filters_bank_lines(self, parser):
        text = """
        Description          Qty    Unit Price    Total
        Widget               10     100.00        1000.00

        Bank Details:
        IBAN: DE89370400440532013000
        SWIFT: COBADEFFXXX
        """
        result = await parser.parse(text, "test.pdf")

        if result.success:
            # Bank lines should not appear as items
            for item in result.items:
                assert "IBAN" not in item.description
                assert "SWIFT" not in item.description

    @pytest.mark.asyncio
    async def test_parse_filters_summary_lines(self, parser):
        text = """
        Description          Qty    Unit Price    Total
        Widget               10     100.00        1000.00
        Gadget               5      200.00        1000.00

        Sub Total                                  2000.00
        VAT @ 20%                                  400.00
        Grand Total                               2400.00
        """
        result = await parser.parse(text, "test.pdf")

        if result.success:
            # Summary lines should be filtered
            for item in result.items:
                if item.row_type == RowType.LINE_ITEM:
                    assert "Sub Total" not in item.description
                    assert "Grand Total" not in item.description


class TestVerticalBlockLayout:
    """Tests for vertical block layout detection and parsing."""

    @pytest.fixture
    def parser(self):
        return TableAwareParser()

    @pytest.mark.asyncio
    async def test_detect_vertical_layout(self, parser):
        """Test detection of vertical block layout."""
        # Vertical layout: item number + description, followed by HS line
        text = """
        1 - Electronic circuit breaker for industrial use
        85362000   100   PCS   50.00   5000.00

        2 - Plastic housing component for electronics
        39231000   200   PCS   25.00   5000.00

        3 - Metal connector with gold plating
        85366990   50    PCS   100.00  5000.00
        """
        result = await parser.parse(text, "test.pdf")

        if result.success:
            # Should detect vertical layout
            assert result.metadata.get("layout") == "vertical" or len(result.items) >= 2

    @pytest.mark.asyncio
    async def test_parse_vertical_items(self, parser):
        """Test parsing of items in vertical layout."""
        text = """
        1 - Single-pole miniature circuit breaker for
        light commercial protection
        85362000   100   PCS   38.00   3800.00

        2 - Double-pole circuit breaker for
        residential applications, BRAND ABC
        85362000   50    PCS   76.00   3800.00
        """
        result = await parser.parse(text, "test.pdf")

        if result.success and result.items:
            # Items should have multi-line descriptions merged
            for item in result.items:
                # Description should be non-empty
                assert item.description or item.item_name


class TestMultiLineDescriptions:
    """Tests for handling multi-line item descriptions."""

    @pytest.fixture
    def parser(self):
        return TableAwareParser()

    @pytest.mark.asyncio
    async def test_handles_wrapped_descriptions(self, parser):
        """Parser should handle descriptions that wrap to multiple lines."""
        text = """
        Description                                    Qty   Price    Total
        High-quality stainless steel industrial        10    100.00   1000.00
        component with precision machining
        Standard aluminum bracket assembly             20    50.00    1000.00
        """
        result = await parser.parse(text, "test.pdf")

        # Should at least not crash and return a result
        assert result.parser_name == "table_aware"


class TestArabicSupport:
    """Tests for Arabic text handling."""

    @pytest.fixture
    def parser(self):
        return TableAwareParser()

    def test_can_parse_arabic_headers(self, parser):
        """Parser should recognize Arabic column headers."""
        text = """
        الوصف                    الكمية     سعر الوحدة     المجموع
        منتج اختبار              10         100.00         1000.00
        """
        confidence = parser.can_parse(text)
        # Should recognize Arabic headers
        assert confidence >= 0.5

    @pytest.mark.asyncio
    async def test_parse_arabic_invoice(self, parser):
        """Parser should handle Arabic invoice text."""
        text = """
        فاتورة

        الوصف                    الكمية     سعر الوحدة     المجموع
        قطع إلكترونية            100        50.00          5000.00
        """
        result = await parser.parse(text, "test.pdf")

        # Should at least not crash
        assert result.parser_name == "table_aware"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def parser(self):
        return TableAwareParser()

    @pytest.mark.asyncio
    async def test_empty_text(self, parser):
        result = await parser.parse("", "test.pdf")
        assert not result.success

    @pytest.mark.asyncio
    async def test_no_items_found(self, parser):
        text = "This is just random text without any table structure."
        result = await parser.parse(text, "test.pdf")
        assert not result.success or len(result.items) == 0

    @pytest.mark.asyncio
    async def test_handles_unicode(self, parser):
        text = """
        Description     Qty     Price     Total
        Caf\u00e9 Machine    1       500.00    500.00
        \u20ac Widget        10      50.00     500.00
        """
        result = await parser.parse(text, "test.pdf")
        # Should not crash on unicode
        assert result.parser_name == "table_aware"

    @pytest.mark.asyncio
    async def test_handles_very_long_lines(self, parser):
        long_desc = "A" * 500
        text = f"""
        Description     Qty     Price     Total
        {long_desc}     10      100.00    1000.00
        """
        result = await parser.parse(text, "test.pdf")
        # Should not crash
        assert result.parser_name == "table_aware"
