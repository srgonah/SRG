"""
Base utilities for invoice parsers.

Common patterns for text normalization, number parsing, date parsing,
confidence scoring, and line filtering.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Bank info detection patterns
BANK_KEYWORDS = [
    "iban",
    "swift",
    "bic",
    "beneficiary",
    "bank",
    "account",
    "acct",
    "branch",
    "remittance",
    "transfer",
    "mt103",
    "mt202",
    "correspondent",
    "intermediary",
    "routing",
    "aba",
    "sort code",
    "clearing",
    # Arabic
    "ايبان",
    "سويفت",
    "بيك",
    "المستفيد",
    "بنك",
    "حساب",
    "فرع",
    "تحويل",
]

BANK_PATTERN = re.compile("|".join(re.escape(w) for w in BANK_KEYWORDS), re.IGNORECASE)
IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
SWIFT_PATTERN = re.compile(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?\b")

# Summary/meta line patterns
SUMMARY_PATTERNS = [
    r"^total\s*:?\s*[\d,\.]+$",
    r"^\s*sub\s*total",
    r"^\s*grand\s*total",
    r"^\s*vat\s*[:@]",
    r"^\s*tax\s*[:@]",
    r"^\s*discount\s*[:@]",
    r"^\s*amount\s+in\s+words",
    r"^\s*payment\s+terms",
    r"^\s*delivery\s+terms",
    r"^\s*incoterms",
    r"^\s*port\s+of\s+",
    r"^\s*country\s+of\s+origin",
    r"^\s*date\s*:\s*\d",
    r"^\s*invoice\s+(no|number|#)",
    r"^\s*page\s+\d+\s+of\s+\d+",
    r"^\s*continued\s+on",
    r"^\s*see\s+attached",
]

SUMMARY_REGEX = re.compile("|".join(SUMMARY_PATTERNS), re.IGNORECASE)


def normalize_unicode(text: str) -> str:
    """Normalize Unicode text to NFKC form."""
    return unicodedata.normalize("NFKC", text)


def normalize_number(value: str) -> str | None:
    """
    Normalize number string by removing thousand separators.

    Handles:
    - "1,234.56" -> "1234.56"
    - "1.234,56" -> "1234.56" (European format)
    - "1 234.56" -> "1234.56" (space separator)
    """
    if not value or not value.strip():
        return None

    # Remove spaces
    cleaned = value.replace(" ", "").strip()

    # Detect format by looking at decimal/thousand separator positions
    comma_pos = cleaned.rfind(",")
    dot_pos = cleaned.rfind(".")

    if comma_pos > dot_pos:
        # European format: 1.234,56
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        # Standard format: 1,234.56
        cleaned = cleaned.replace(",", "")

    # Remove any remaining non-numeric chars except . and -
    cleaned = re.sub(r"[^\d.\-]", "", cleaned)

    return cleaned if cleaned else None


def parse_number(value: str | None) -> float | None:
    """
    Parse a number string to float.

    Handles various formats and returns None for invalid values.
    """
    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        return float(value)

    normalized = normalize_number(str(value))
    if not normalized:
        return None

    try:
        return float(normalized)
    except ValueError:
        return None


def is_bank_line(text: str) -> bool:
    """
    Check if a line contains bank information.

    Used to filter bank details from item extraction.
    """
    if not text:
        return False

    t = text.strip().lower()

    # Check keywords
    if BANK_PATTERN.search(t):
        return True

    # Check IBAN pattern
    if IBAN_PATTERN.search(text):
        return True

    # Check SWIFT pattern
    if SWIFT_PATTERN.search(text):
        return True

    return False


def is_summary_or_meta_line(text: str) -> bool:
    """
    Check if a line is a summary row or metadata.

    Used to filter non-item rows from table parsing.
    """
    if not text:
        return True

    t = text.strip()
    if len(t) < 3:
        return True

    return bool(SUMMARY_REGEX.match(t))


def is_hs_code(text: str) -> bool:
    """Check if text looks like an HS code (6-10 digits)."""
    if not text:
        return False
    cleaned = text.replace(".", "").replace(" ", "")
    return bool(re.match(r"^\d{6,10}$", cleaned))


def extract_hs_code(text: str) -> str | None:
    """Extract HS code from text."""
    match = re.search(r"\b(\d{6,10})\b", text.replace(".", ""))
    return match.group(1) if match else None


def clean_item_name(name: str) -> str:
    """
    Clean item name by removing noise.

    - Removes leading/trailing whitespace
    - Collapses multiple spaces
    - Removes line numbers
    """
    if not name:
        return ""

    # Normalize unicode
    name = normalize_unicode(name)

    # Remove leading line numbers (1., 1-, 1), etc.)
    name = re.sub(r"^\s*\d+[\.\-\)]\s*", "", name)

    # Collapse whitespace
    name = " ".join(name.split())

    return name.strip()


def extract_table_block(text: str) -> str:
    """
    Extract the main table block from invoice text.

    Removes headers before items and bank forms after items.
    """
    lines = text.split("\n")

    # Find table start (first line with qty/price patterns)
    start_idx = 0
    for i, line in enumerate(lines):
        # Look for lines with numbers that look like qty and prices
        if re.search(r"\d+(?:\.\d+)?\s+\d+(?:\.\d+)?", line):
            start_idx = max(0, i - 2)  # Include potential header
            break

    # Find table end (bank form or summary section)
    end_idx = len(lines)
    for i in range(len(lines) - 1, start_idx, -1):
        line = lines[i].lower()
        if any(
            kw in line for kw in ["bank details", "remittance", "iban:", "swift:", "beneficiary"]
        ):
            end_idx = i
            break
        if "grand total" in line or "amount in words" in line:
            end_idx = i + 1
            break

    return "\n".join(lines[start_idx:end_idx])


def split_cells_by_whitespace(line: str, min_gap: int = 2) -> list[dict[str, Any]]:
    """
    Split a line into cells based on whitespace gaps.

    Args:
        line: Text line
        min_gap: Minimum spaces to consider a cell boundary

    Returns:
        List of {text, start_pos, end_pos} dicts
    """
    cells = []
    current_cell = ""
    current_start = 0
    space_count = 0

    for i, char in enumerate(line):
        if char in " \t":
            space_count += 1
            if space_count >= min_gap and current_cell.strip():
                cells.append(
                    {
                        "text": current_cell.strip(),
                        "start_pos": current_start,
                        "end_pos": i - space_count,
                    }
                )
                current_cell = ""
                current_start = -1
        else:
            if current_start == -1:
                current_start = i
            if space_count > 0 and space_count < min_gap:
                current_cell += " " * space_count
            space_count = 0
            current_cell += char

    # Add last cell
    if current_cell.strip():
        cells.append(
            {
                "text": current_cell.strip(),
                "start_pos": current_start
                if current_start != -1
                else len(line) - len(current_cell.strip()),
                "end_pos": len(line),
            }
        )

    return cells


# ============================================================================
# Date Parsing
# ============================================================================

DATE_PATTERNS = [
    # ISO format: 2024-01-15
    (r"(\d{4})-(\d{1,2})-(\d{1,2})", "%Y-%m-%d"),
    # European: 15/01/2024, 15.01.2024
    (r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", "%d/%m/%Y"),
    # US: 01/15/2024
    (r"(\d{1,2})/(\d{1,2})/(\d{4})", "%m/%d/%Y"),
    # Long: 15 January 2024, Jan 15, 2024
    (r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*,?\s*(\d{4})", None),
    (r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})\s*,?\s*(\d{4})", None),
]

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def parse_date(text: str | None) -> str | None:
    """
    Parse various date formats into ISO format (YYYY-MM-DD).

    Handles:
    - ISO: 2024-01-15
    - European: 15/01/2024, 15.01.2024
    - US: 01/15/2024
    - Long: January 15, 2024 / 15 January 2024

    Returns:
        ISO date string or None if parsing fails
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Try ISO format first
    iso_match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if iso_match:
        try:
            year, month, day = map(int, iso_match.groups())
            return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            pass

    # Try numeric formats: DD/MM/YYYY or MM/DD/YYYY
    numeric_match = re.match(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", text)
    if numeric_match:
        a, b, year = map(int, numeric_match.groups())
        # Heuristic: if first number > 12, it's day (European format)
        if a > 12:
            day, month = a, b
        elif b > 12:
            month, day = a, b
        else:
            # Assume European (day/month/year) - most common in invoices
            day, month = a, b

        try:
            datetime(year, month, day)
            return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            # Try swapped
            try:
                datetime(year, day, month)
                return f"{year:04d}-{day:02d}-{month:02d}"
            except ValueError:
                pass

    # Try long formats with month names
    # Pattern: Day Month Year (15 January 2024)
    long_match1 = re.search(
        r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*,?\s*(\d{4})",
        text,
        re.IGNORECASE,
    )
    if long_match1:
        day = int(long_match1.group(1))
        month = MONTH_MAP.get(long_match1.group(2).lower()[:3], 0)
        year = int(long_match1.group(3))
        if month:
            try:
                datetime(year, month, day)
                return f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                pass

    # Pattern: Month Day, Year (January 15, 2024)
    long_match2 = re.search(
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})\s*,?\s*(\d{4})",
        text,
        re.IGNORECASE,
    )
    if long_match2:
        month = MONTH_MAP.get(long_match2.group(1).lower()[:3], 0)
        day = int(long_match2.group(2))
        year = int(long_match2.group(3))
        if month:
            try:
                datetime(year, month, day)
                return f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                pass

    return None


# ============================================================================
# Confidence Scoring
# ============================================================================

@dataclass
class ConfidenceFactors:
    """Factors contributing to parser confidence score."""

    has_invoice_number: bool = False
    has_invoice_date: bool = False
    has_seller_name: bool = False
    has_buyer_name: bool = False
    has_total_amount: bool = False
    items_count: int = 0
    items_with_quantity: int = 0
    items_with_prices: int = 0
    items_with_hs_code: int = 0
    arithmetic_correct: bool = True
    template_matched: bool = False
    template_confidence: float = 0.0


def calculate_confidence(factors: ConfidenceFactors) -> float:
    """
    Calculate parsing confidence score (0.0 to 1.0).

    Scoring breakdown:
    - Invoice metadata (40% max):
      - Invoice number: 10%
      - Invoice date: 10%
      - Seller name: 10%
      - Buyer/total: 10%
    - Line items quality (40% max):
      - Has items: 10%
      - Items with quantities: 15%
      - Items with prices: 15%
    - Validation (20% max):
      - HS codes present: 10%
      - Arithmetic correct: 10%

    Template match can boost final score.
    """
    score = 0.0

    # Metadata factors (40%)
    if factors.has_invoice_number:
        score += 0.10
    if factors.has_invoice_date:
        score += 0.10
    if factors.has_seller_name:
        score += 0.10
    if factors.has_buyer_name or factors.has_total_amount:
        score += 0.10

    # Items quality (40%)
    if factors.items_count > 0:
        score += 0.10

        # Quantity coverage
        qty_ratio = factors.items_with_quantity / factors.items_count
        score += 0.15 * qty_ratio

        # Price coverage
        price_ratio = factors.items_with_prices / factors.items_count
        score += 0.15 * price_ratio

    # Validation factors (20%)
    if factors.items_count > 0 and factors.items_with_hs_code > 0:
        hs_ratio = factors.items_with_hs_code / factors.items_count
        score += 0.10 * hs_ratio

    if factors.arithmetic_correct:
        score += 0.10

    # Template match boost (up to 10% bonus)
    if factors.template_matched:
        score += 0.10 * factors.template_confidence

    return min(1.0, max(0.0, score))


def calculate_item_confidence(item: dict[str, Any]) -> float:
    """
    Calculate confidence for a single line item.

    Returns 0-1 based on completeness:
    - Description: 20%
    - Quantity: 25%
    - Unit price: 25%
    - Total price: 20%
    - HS code: 10%
    """
    score = 0.0

    if item.get("description") or item.get("item_name"):
        score += 0.20

    qty = item.get("quantity")
    if qty is not None and qty > 0:
        score += 0.25

    unit_price = item.get("unit_price")
    if unit_price is not None and unit_price > 0:
        score += 0.25

    total_price = item.get("total_price")
    if total_price is not None and total_price > 0:
        score += 0.20

    if item.get("hs_code"):
        score += 0.10

    return score


# ============================================================================
# Enhanced Parser Result
# ============================================================================

@dataclass
class ParserTiming:
    """Timing information for a parser attempt."""

    parser_name: str
    started_at: datetime
    ended_at: datetime
    duration_ms: float
    success: bool
    confidence: float = 0.0
    error: str | None = None


@dataclass
class EnhancedParserResult:
    """
    Enhanced result from invoice parsing with warnings and timings.

    Extends the core ParserResult with additional context for debugging
    and quality assessment.
    """

    success: bool
    invoice: Any | None = None  # Invoice entity
    items: list[Any] = field(default_factory=list)
    confidence: float = 0.0
    parser_name: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Enhanced fields
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    timings: list[ParserTiming] = field(default_factory=list)
    confidence_factors: ConfidenceFactors | None = None

    @property
    def total_parse_time_ms(self) -> float:
        """Total time spent across all parser attempts."""
        return sum(t.duration_ms for t in self.timings)

    @property
    def parsers_tried(self) -> list[str]:
        """Names of all parsers that were attempted."""
        return [t.parser_name for t in self.timings]

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        if message not in self.warnings:
            self.warnings.append(message)

    def add_note(self, message: str) -> None:
        """Add an informational note."""
        if message not in self.notes:
            self.notes.append(message)

    def add_timing(
        self,
        parser_name: str,
        started_at: datetime,
        ended_at: datetime,
        success: bool,
        confidence: float = 0.0,
        error: str | None = None,
    ) -> None:
        """Record timing for a parser attempt."""
        duration_ms = (ended_at - started_at).total_seconds() * 1000
        self.timings.append(
            ParserTiming(
                parser_name=parser_name,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=duration_ms,
                success=success,
                confidence=confidence,
                error=error,
            )
        )


# ============================================================================
# Currency Parsing
# ============================================================================

CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
    "د.ج": "DZD",
    "دج": "DZD",
    "DA": "DZD",
}

CURRENCY_CODES = [
    "USD", "EUR", "GBP", "JPY", "CNY", "INR", "AED", "SAR", "DZD",
    "EGP", "MAD", "TND", "LYD", "KWD", "BHD", "OMR", "QAR", "JOD",
]


def detect_currency(text: str) -> str:
    """
    Detect currency from text.

    Returns ISO currency code (default: USD).
    """
    if not text:
        return "USD"

    # Check for symbols
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code

    # Check for codes
    text_upper = text.upper()
    for code in CURRENCY_CODES:
        if code in text_upper:
            return code

    return "USD"


def strip_currency(value: str) -> str:
    """Remove currency symbols/codes from a value string."""
    if not value:
        return ""

    result = value
    for symbol in CURRENCY_SYMBOLS:
        result = result.replace(symbol, "")
    for code in CURRENCY_CODES:
        result = re.sub(rf"\b{code}\b", "", result, flags=re.IGNORECASE)

    return result.strip()


# ============================================================================
# Safe String Cleanup
# ============================================================================

def safe_string(value: Any, max_length: int = 1000) -> str:
    """
    Safely convert value to string with cleanup.

    - Handles None
    - Normalizes Unicode
    - Trims whitespace
    - Enforces max length
    """
    if value is None:
        return ""

    s = str(value)
    s = normalize_unicode(s)
    s = " ".join(s.split())  # Collapse whitespace

    if len(s) > max_length:
        s = s[:max_length] + "..."

    return s
