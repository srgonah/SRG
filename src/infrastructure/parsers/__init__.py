"""Parser infrastructure implementations."""

from src.infrastructure.parsers.base import (
    ConfidenceFactors,
    # Enhanced result types
    EnhancedParserResult,
    ParserTiming,
    # Confidence scoring
    calculate_confidence,
    calculate_item_confidence,
    # Text utilities
    clean_item_name,
    # Currency
    detect_currency,
    extract_hs_code,
    extract_table_block,
    is_bank_line,
    is_summary_or_meta_line,
    normalize_number,
    normalize_unicode,
    # Date parsing
    parse_date,
    parse_number,
    safe_string,
    split_cells_by_whitespace,
    strip_currency,
)
from src.infrastructure.parsers.registry import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    ParserRegistry,
    get_parser_registry,
    reset_parser_registry,
)
from src.infrastructure.parsers.table_aware_parser import (
    TableAwareParser,
    get_table_aware_parser,
)
from src.infrastructure.parsers.template_parser import (
    TemplateDetector,
    TemplateParser,
    get_template_detector,
    get_template_parser,
)
from src.infrastructure.parsers.vision_parser import (
    VisionInvoiceResponse,
    VisionLineItem,
    VisionParser,
    get_vision_parser,
)

__all__ = [
    # Base utilities
    "parse_number",
    "normalize_number",
    "normalize_unicode",
    "clean_item_name",
    "is_bank_line",
    "is_summary_or_meta_line",
    "extract_hs_code",
    "extract_table_block",
    "split_cells_by_whitespace",
    "safe_string",
    "strip_currency",
    # Date parsing
    "parse_date",
    # Currency
    "detect_currency",
    # Confidence scoring
    "calculate_confidence",
    "calculate_item_confidence",
    "ConfidenceFactors",
    # Enhanced result types
    "EnhancedParserResult",
    "ParserTiming",
    # Template parser
    "TemplateParser",
    "TemplateDetector",
    "get_template_parser",
    "get_template_detector",
    # Table parser
    "TableAwareParser",
    "get_table_aware_parser",
    # Vision parser
    "VisionParser",
    "VisionInvoiceResponse",
    "VisionLineItem",
    "get_vision_parser",
    # Registry
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "ParserRegistry",
    "get_parser_registry",
    "reset_parser_registry",
]
