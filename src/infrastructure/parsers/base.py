"""
Base utilities for invoice parsers.

Common patterns for text normalization, number parsing, and line filtering.
"""

import re
import unicodedata

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


def split_cells_by_whitespace(line: str, min_gap: int = 2) -> list[dict]:
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
