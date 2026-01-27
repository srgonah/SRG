"""
Parser registry for strategy pattern orchestration.

Manages multiple parsers and routes parsing to the best available strategy.
Uses a deterministic parsing chain: Template (100) → Table-aware (80) → Vision (60).
"""

from datetime import UTC, datetime
from typing import Any

from src.config import get_logger
from src.core.interfaces import IInvoiceParser, IParserRegistry, ParserResult
from src.infrastructure.parsers.base import ParserTiming
from src.infrastructure.parsers.table_aware_parser import get_table_aware_parser
from src.infrastructure.parsers.template_parser import get_template_parser
from src.infrastructure.parsers.vision_parser import get_vision_parser

logger = get_logger(__name__)

# Default confidence threshold for early stopping
DEFAULT_CONFIDENCE_THRESHOLD = 0.75


class ParserRegistry(IParserRegistry):
    """
    Registry for invoice parsers with confidence-based fallback.

    Manages parser selection and orchestrates parsing attempts.
    Uses deterministic ordering by priority (highest first).

    Parsing chain: Template (100) → Table-aware (80) → Vision (60)
    """

    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ):
        """
        Initialize parser registry.

        Args:
            confidence_threshold: Minimum confidence to accept result
                                  and stop trying other parsers.
        """
        self._parsers: list[IInvoiceParser] = []
        self._confidence_threshold = confidence_threshold

    @property
    def confidence_threshold(self) -> float:
        """Get the confidence threshold for early stopping."""
        return self._confidence_threshold

    @confidence_threshold.setter
    def confidence_threshold(self, value: float) -> None:
        """Set confidence threshold (clamped to 0-1)."""
        self._confidence_threshold = max(0.0, min(1.0, value))

    def register(self, parser: IInvoiceParser) -> None:
        """
        Register a parser implementation.

        Parsers are inserted in priority order (highest first).
        """
        # Check for duplicates
        for existing in self._parsers:
            if existing.name == parser.name:
                logger.warning(
                    "parser_already_registered",
                    name=parser.name,
                )
                return

        # Insert in priority order (descending)
        inserted = False
        for i, existing in enumerate(self._parsers):
            if parser.priority > existing.priority:
                self._parsers.insert(i, parser)
                inserted = True
                break

        if not inserted:
            self._parsers.append(parser)

        logger.info(
            "parser_registered",
            parser_name=parser.name,
            priority=parser.priority,
            total_parsers=len(self._parsers),
        )

    def unregister(self, parser_name: str) -> bool:
        """Unregister a parser by name."""
        for i, parser in enumerate(self._parsers):
            if parser.name == parser_name:
                del self._parsers[i]
                logger.info(
                    "parser_unregistered",
                    parser_name=parser_name,
                    remaining_parsers=len(self._parsers),
                )
                return True
        return False

    def get_parsers(self) -> list[IInvoiceParser]:
        """Get all registered parsers sorted by priority (descending)."""
        return list(self._parsers)

    def get_parser(self, name: str) -> IInvoiceParser | None:
        """Get a specific parser by name."""
        for parser in self._parsers:
            if parser.name == name:
                return parser
        return None

    async def parse(
        self,
        text: str,
        filename: str,
        hints: dict[str, Any] | None = None,
    ) -> ParserResult:
        """
        Parse using the best available parser.

        Tries parsers in priority order:
        1. Template parser (priority 100) - if template matches
        2. Table-aware parser (priority 80) - for structured tables
        3. Vision parser (priority 60) - for complex/scanned docs

        Stops early if a parser returns confidence >= threshold.
        Falls back to next parser if confidence is below threshold.

        Args:
            text: Invoice text content
            filename: Original filename
            hints: Optional parsing hints (e.g., image_path, prefer_vision)

        Returns:
            ParserResult from best successful parser
        """
        hints = hints or {}

        if not self._parsers:
            return ParserResult(
                success=False,
                parser_name="registry",
                error="No parsers registered",
            )

        best_result: ParserResult | None = None
        timings: list[ParserTiming] = []
        errors: list[str] = []

        # Try each parser in priority order
        for parser in self._parsers:
            start_time = datetime.now(UTC)

            # Check if parser can handle this content
            can_parse_confidence = parser.can_parse(text, hints)

            if can_parse_confidence < 0.1:
                logger.debug(
                    "parser_skipped",
                    parser_name=parser.name,
                    can_parse_confidence=can_parse_confidence,
                    filename=filename,
                )
                continue

            logger.info(
                "parser_attempt_start",
                parser_name=parser.name,
                priority=parser.priority,
                can_parse_confidence=can_parse_confidence,
                filename=filename,
            )

            try:
                result = await parser.parse(text, filename, hints)
                end_time = datetime.now(UTC)
                duration_ms = (end_time - start_time).total_seconds() * 1000

                # Record timing
                timings.append(
                    ParserTiming(
                        parser_name=parser.name,
                        started_at=start_time,
                        ended_at=end_time,
                        duration_ms=duration_ms,
                        success=result.success,
                        confidence=result.confidence,
                        error=result.error,
                    )
                )

                if result.success:
                    logger.info(
                        "parser_attempt_success",
                        parser_name=parser.name,
                        items_count=len(result.items) if result.items else 0,
                        confidence=result.confidence,
                        duration_ms=round(duration_ms, 2),
                        filename=filename,
                    )

                    # Track best result
                    if best_result is None or result.confidence > best_result.confidence:
                        best_result = result

                    # Early stop if confidence meets threshold
                    if result.confidence >= self._confidence_threshold:
                        logger.info(
                            "parser_early_stop",
                            parser_name=parser.name,
                            confidence=result.confidence,
                            threshold=self._confidence_threshold,
                            filename=filename,
                        )
                        # Add timing info to metadata
                        result.metadata = result.metadata or {}
                        result.metadata["timings"] = [
                            {
                                "parser": t.parser_name,
                                "duration_ms": round(t.duration_ms, 2),
                                "success": t.success,
                                "confidence": t.confidence,
                            }
                            for t in timings
                        ]
                        return result

                    logger.info(
                        "parser_confidence_below_threshold",
                        parser_name=parser.name,
                        confidence=result.confidence,
                        threshold=self._confidence_threshold,
                        filename=filename,
                    )
                else:
                    logger.debug(
                        "parser_attempt_failed",
                        parser_name=parser.name,
                        error=result.error,
                        duration_ms=round(duration_ms, 2),
                        filename=filename,
                    )
                    if result.error:
                        errors.append(f"{parser.name}: {result.error}")

            except Exception as e:
                end_time = datetime.now(UTC)
                duration_ms = (end_time - start_time).total_seconds() * 1000

                timings.append(
                    ParserTiming(
                        parser_name=parser.name,
                        started_at=start_time,
                        ended_at=end_time,
                        duration_ms=duration_ms,
                        success=False,
                        confidence=0.0,
                        error=str(e),
                    )
                )

                logger.error(
                    "parser_exception",
                    parser_name=parser.name,
                    error=str(e),
                    duration_ms=round(duration_ms, 2),
                    filename=filename,
                )
                errors.append(f"{parser.name}: {str(e)}")
                continue

        # Return best result if any parser succeeded (even below threshold)
        if best_result is not None:
            logger.info(
                "parser_returning_best_result",
                parser_name=best_result.parser_name,
                confidence=best_result.confidence,
                parsers_tried=len(timings),
                filename=filename,
            )
            best_result.metadata = best_result.metadata or {}
            best_result.metadata["timings"] = [
                {
                    "parser": t.parser_name,
                    "duration_ms": round(t.duration_ms, 2),
                    "success": t.success,
                    "confidence": t.confidence,
                }
                for t in timings
            ]
            best_result.metadata["below_threshold"] = True
            return best_result

        # All parsers failed
        logger.error(
            "all_parsers_failed",
            parsers_tried=len(timings),
            errors=errors,
            filename=filename,
        )

        return ParserResult(
            success=False,
            parser_name="registry",
            error=f"All parsers failed: {'; '.join(errors) if errors else 'No parsers could handle this content'}",
            metadata={
                "timings": [
                    {
                        "parser": t.parser_name,
                        "duration_ms": round(t.duration_ms, 2),
                        "success": t.success,
                        "error": t.error,
                    }
                    for t in timings
                ]
            },
        )

    async def parse_with_parser(
        self,
        parser_name: str,
        text: str,
        filename: str,
        hints: dict[str, Any] | None = None,
    ) -> ParserResult:
        """
        Parse using a specific parser by name.

        Useful for testing or when a specific parser is preferred.
        """
        parser = self.get_parser(parser_name)
        if parser is None:
            return ParserResult(
                success=False,
                parser_name="registry",
                error=f"Parser '{parser_name}' not found",
            )

        return await parser.parse(text, filename, hints or {})


# Singleton registry with default parsers
_registry: ParserRegistry | None = None


def get_parser_registry() -> ParserRegistry:
    """Get or create the global parser registry with default parsers."""
    global _registry

    if _registry is None:
        _registry = ParserRegistry()

        # Register default parsers in priority order
        _registry.register(get_template_parser())
        _registry.register(get_table_aware_parser())
        _registry.register(get_vision_parser())

        logger.info(
            "parser_registry_initialized",
            parsers=[p.name for p in _registry.get_parsers()],
        )

    return _registry


def reset_parser_registry() -> None:
    """Reset the parser registry (for testing)."""
    global _registry
    _registry = None
