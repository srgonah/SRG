"""
Unit tests for ParserRegistry parsing chain.

Tests:
- Correct parser ordering: template (100) -> table (80) -> vision (60)
- Fallback behavior when confidence is below threshold
- Early stopping when confidence meets threshold
- Timing information is recorded
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.entities import Invoice, LineItem, RowType
from src.core.interfaces import ParserResult
from src.infrastructure.parsers.registry import (
    ParserRegistry,
    DEFAULT_CONFIDENCE_THRESHOLD,
)


class MockParser:
    """Mock parser for testing registry behavior."""

    def __init__(
        self,
        name: str,
        priority: int,
        can_parse_result: float = 0.5,
        parse_success: bool = True,
        parse_confidence: float = 0.8,
        parse_error: str | None = None,
    ):
        self._name = name
        self._priority = priority
        self._can_parse_result = can_parse_result
        self._parse_success = parse_success
        self._parse_confidence = parse_confidence
        self._parse_error = parse_error
        self.parse_called = False
        self.can_parse_called = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    def can_parse(self, text: str, hints: dict | None = None) -> float:
        self.can_parse_called = True
        return self._can_parse_result

    async def parse(
        self,
        text: str,
        filename: str,
        hints: dict | None = None,
    ) -> ParserResult:
        self.parse_called = True
        if self._parse_success:
            return ParserResult(
                success=True,
                invoice=Invoice(invoice_no="TEST-001"),
                items=[
                    LineItem(
                        line_number=1,
                        item_name="Test Item",
                        quantity=10.0,
                        unit_price=100.0,
                        total_price=1000.0,
                    )
                ],
                confidence=self._parse_confidence,
                parser_name=self._name,
            )
        else:
            return ParserResult(
                success=False,
                parser_name=self._name,
                error=self._parse_error or "Parse failed",
            )


class TestParserOrdering:
    """Tests for parser priority ordering."""

    def test_parsers_registered_in_priority_order(self):
        """Parsers should be stored in descending priority order."""
        registry = ParserRegistry()

        # Register in random order
        parser_80 = MockParser("table", 80)
        parser_100 = MockParser("template", 100)
        parser_60 = MockParser("vision", 60)

        registry.register(parser_60)
        registry.register(parser_100)
        registry.register(parser_80)

        parsers = registry.get_parsers()
        priorities = [p.priority for p in parsers]

        assert priorities == [100, 80, 60], "Parsers should be sorted by priority (descending)"

    def test_correct_order_template_table_vision(self):
        """Default order should be: template (100) -> table (80) -> vision (60)."""
        registry = ParserRegistry()

        template = MockParser("template", 100)
        table = MockParser("table_aware", 80)
        vision = MockParser("vision", 60)

        registry.register(template)
        registry.register(table)
        registry.register(vision)

        parsers = registry.get_parsers()
        names = [p.name for p in parsers]

        assert names == ["template", "table_aware", "vision"]

    def test_duplicate_parser_not_registered(self):
        """Same parser name should not be registered twice."""
        registry = ParserRegistry()

        parser1 = MockParser("template", 100)
        parser2 = MockParser("template", 100)

        registry.register(parser1)
        registry.register(parser2)

        assert len(registry.get_parsers()) == 1


class TestFallbackBehavior:
    """Tests for fallback when confidence is below threshold."""

    @pytest.mark.asyncio
    async def test_fallback_when_confidence_below_threshold(self):
        """Should try next parser if confidence is below threshold."""
        registry = ParserRegistry(confidence_threshold=0.8)

        # Template returns low confidence
        template = MockParser("template", 100, parse_confidence=0.5)
        # Table returns high confidence
        table = MockParser("table", 80, parse_confidence=0.9)

        registry.register(template)
        registry.register(table)

        result = await registry.parse("test text", "test.pdf")

        assert result.success
        assert result.parser_name == "table"
        assert result.confidence == 0.9
        assert template.parse_called
        assert table.parse_called

    @pytest.mark.asyncio
    async def test_returns_best_result_when_all_below_threshold(self):
        """Should return best result even if all below threshold."""
        registry = ParserRegistry(confidence_threshold=0.9)

        template = MockParser("template", 100, parse_confidence=0.6)
        table = MockParser("table", 80, parse_confidence=0.7)
        vision = MockParser("vision", 60, parse_confidence=0.5)

        registry.register(template)
        registry.register(table)
        registry.register(vision)

        result = await registry.parse("test text", "test.pdf")

        assert result.success
        # Should return table's result (highest confidence)
        assert result.parser_name == "table"
        assert result.confidence == 0.7
        assert result.metadata.get("below_threshold") is True

    @pytest.mark.asyncio
    async def test_skips_parser_when_can_parse_returns_low(self):
        """Should skip parser if can_parse returns < 0.1."""
        registry = ParserRegistry()

        # Template can't parse (returns 0.0)
        template = MockParser("template", 100, can_parse_result=0.0)
        # Table can parse
        table = MockParser("table", 80, can_parse_result=0.5)

        registry.register(template)
        registry.register(table)

        result = await registry.parse("test text", "test.pdf")

        assert result.success
        assert template.can_parse_called
        assert not template.parse_called  # Should not attempt parse
        assert table.parse_called


class TestEarlyStop:
    """Tests for early stopping when confidence meets threshold."""

    @pytest.mark.asyncio
    async def test_stops_at_first_high_confidence(self):
        """Should stop trying parsers when one returns >= threshold."""
        registry = ParserRegistry(confidence_threshold=0.75)

        template = MockParser("template", 100, parse_confidence=0.85)
        table = MockParser("table", 80, parse_confidence=0.9)

        registry.register(template)
        registry.register(table)

        result = await registry.parse("test text", "test.pdf")

        assert result.success
        assert result.parser_name == "template"
        assert template.parse_called
        assert not table.parse_called  # Should not be tried

    @pytest.mark.asyncio
    async def test_continues_after_parse_failure(self):
        """Should try next parser if current one fails."""
        registry = ParserRegistry()

        template = MockParser("template", 100, parse_success=False)
        table = MockParser("table", 80, parse_success=True, parse_confidence=0.8)

        registry.register(template)
        registry.register(table)

        result = await registry.parse("test text", "test.pdf")

        assert result.success
        assert result.parser_name == "table"
        assert template.parse_called
        assert table.parse_called


class TestTimingInformation:
    """Tests for timing recording."""

    @pytest.mark.asyncio
    async def test_timings_recorded_in_metadata(self):
        """Should record timing for each parser attempt."""
        registry = ParserRegistry(confidence_threshold=0.9)

        template = MockParser("template", 100, parse_confidence=0.6)
        table = MockParser("table", 80, parse_confidence=0.7)

        registry.register(template)
        registry.register(table)

        result = await registry.parse("test text", "test.pdf")

        assert "timings" in result.metadata
        timings = result.metadata["timings"]

        assert len(timings) == 2
        assert timings[0]["parser"] == "template"
        assert timings[1]["parser"] == "table"
        assert all("duration_ms" in t for t in timings)
        assert all("success" in t for t in timings)

    @pytest.mark.asyncio
    async def test_timing_includes_failed_attempts(self):
        """Should record timing even for failed parser attempts."""
        registry = ParserRegistry()

        template = MockParser("template", 100, parse_success=False)
        table = MockParser("table", 80, parse_success=True)

        registry.register(template)
        registry.register(table)

        result = await registry.parse("test text", "test.pdf")

        timings = result.metadata["timings"]
        assert timings[0]["parser"] == "template"
        assert timings[0]["success"] is False
        assert timings[1]["parser"] == "table"
        assert timings[1]["success"] is True


class TestErrorHandling:
    """Tests for error handling in registry."""

    @pytest.mark.asyncio
    async def test_handles_parser_exception(self):
        """Should handle exceptions from parsers gracefully."""
        registry = ParserRegistry()

        class ExceptionParser:
            name = "exception"
            priority = 100

            def can_parse(self, text, hints=None):
                return 0.5

            async def parse(self, text, filename, hints=None):
                raise ValueError("Parser exploded")

        table = MockParser("table", 80, parse_success=True)

        registry.register(ExceptionParser())
        registry.register(table)

        result = await registry.parse("test text", "test.pdf")

        # Should recover and return table result
        assert result.success
        assert result.parser_name == "table"

    @pytest.mark.asyncio
    async def test_all_parsers_fail_returns_error(self):
        """Should return error result when all parsers fail."""
        registry = ParserRegistry()

        template = MockParser("template", 100, parse_success=False, parse_error="Template error")
        table = MockParser("table", 80, parse_success=False, parse_error="Table error")

        registry.register(template)
        registry.register(table)

        result = await registry.parse("test text", "test.pdf")

        assert not result.success
        assert "All parsers failed" in result.error
        assert "template: Template error" in result.error
        assert "table: Table error" in result.error

    @pytest.mark.asyncio
    async def test_no_parsers_registered(self):
        """Should return error when no parsers are registered."""
        registry = ParserRegistry()

        result = await registry.parse("test text", "test.pdf")

        assert not result.success
        assert "No parsers registered" in result.error


class TestSpecificParserSelection:
    """Tests for parse_with_parser method."""

    @pytest.mark.asyncio
    async def test_parse_with_specific_parser(self):
        """Should allow parsing with a specific parser by name."""
        registry = ParserRegistry()

        template = MockParser("template", 100)
        table = MockParser("table", 80)

        registry.register(template)
        registry.register(table)

        result = await registry.parse_with_parser("table", "test text", "test.pdf")

        assert result.success
        assert result.parser_name == "table"
        assert not template.parse_called

    @pytest.mark.asyncio
    async def test_parse_with_unknown_parser(self):
        """Should return error for unknown parser name."""
        registry = ParserRegistry()

        result = await registry.parse_with_parser("unknown", "test text", "test.pdf")

        assert not result.success
        assert "not found" in result.error
