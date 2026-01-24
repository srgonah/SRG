"""
Parser registry for strategy pattern orchestration.

Manages multiple parsers and routes parsing to the best available strategy.
"""

from src.config import get_logger
from src.core.interfaces import IInvoiceParser, IParserRegistry, ParserResult
from src.infrastructure.parsers.table_aware_parser import get_table_aware_parser
from src.infrastructure.parsers.template_parser import get_template_parser
from src.infrastructure.parsers.vision_parser import get_vision_parser

logger = get_logger(__name__)


class ParserRegistry(IParserRegistry):
    """
    Registry for invoice parsers.

    Manages parser selection and orchestrates parsing attempts.
    """

    def __init__(self):
        self._parsers: list[IInvoiceParser] = []

    def register(self, parser: IInvoiceParser) -> None:
        """Register a parser implementation."""
        # Insert in priority order
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
            name=parser.name,
            priority=parser.priority,
        )

    def unregister(self, parser_name: str) -> bool:
        """Unregister a parser by name."""
        for i, parser in enumerate(self._parsers):
            if parser.name == parser_name:
                del self._parsers[i]
                logger.info("parser_unregistered", name=parser_name)
                return True
        return False

    def get_parsers(self) -> list[IInvoiceParser]:
        """Get all registered parsers sorted by priority."""
        return list(self._parsers)

    async def parse(
        self,
        text: str,
        filename: str,
        hints: dict | None = None,
    ) -> ParserResult:
        """
        Parse using the best available parser.

        Tries parsers in priority order:
        1. Template parser (priority 100) - if template matches
        2. Table-aware parser (priority 80) - for structured tables
        3. Vision parser (priority 60) - for complex/scanned docs

        Returns result from first successful parser.
        """
        hints = hints or {}

        if not self._parsers:
            return ParserResult(
                success=False,
                parser_name="registry",
                error="No parsers registered",
            )

        # Try each parser in priority order
        for parser in self._parsers:
            # Check if parser can handle this content
            confidence = parser.can_parse(text, hints)

            if confidence < 0.1:
                logger.debug(
                    "parser_skipped",
                    parser=parser.name,
                    confidence=confidence,
                )
                continue

            logger.info(
                "trying_parser",
                parser=parser.name,
                priority=parser.priority,
                confidence=confidence,
            )

            try:
                result = await parser.parse(text, filename, hints)

                if result.success:
                    logger.info(
                        "parser_success",
                        parser=parser.name,
                        items=len(result.items) if result.items else 0,
                        confidence=result.confidence,
                    )
                    return result

                logger.debug(
                    "parser_failed",
                    parser=parser.name,
                    error=result.error,
                )

            except Exception as e:
                logger.error(
                    "parser_error",
                    parser=parser.name,
                    error=str(e),
                )
                continue

        # All parsers failed
        return ParserResult(
            success=False,
            parser_name="registry",
            error="All parsers failed to extract invoice data",
        )


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
