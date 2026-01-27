"""
Table-aware invoice parser.

Handles complex invoice layouts with column detection and multi-line descriptions.
"""

import re
from typing import Any

from src.config import get_logger
from src.core.entities import Invoice, LineItem, RowType
from src.core.interfaces import IInvoiceParser, ParserResult
from src.infrastructure.parsers.base import (
    clean_item_name,
    extract_hs_code,
    extract_table_block,
    is_bank_line,
    is_summary_or_meta_line,
    parse_number,
    split_cells_by_whitespace,
)

logger = get_logger(__name__)


# Column header patterns
HEADER_PATTERNS = {
    "description": [
        "description",
        "item",
        "goods",
        "product",
        "particulars",
        "الوصف",
        "بيان",
        "الصنف",
    ],
    "quantity": [
        "qty",
        "quantity",
        "q.t.y",
        "qnty",
        "pcs",
        "الكمية",
        "عدد",
    ],
    "unit": [
        "unit",
        "uom",
        "u/m",
        "الوحدة",
    ],
    "unit_price": [
        "unit price",
        "price",
        "u/price",
        "rate",
        "سعر الوحدة",
        "السعر",
    ],
    "total_price": [
        "amount",
        "total",
        "line total",
        "value",
        "المجموع",
        "القيمة",
        "الإجمالي",
    ],
    "hs_code": [
        "hs code",
        "hs",
        "tariff",
        "hscode",
        "الرمز الجمركي",
    ],
}


class TableAwareParser(IInvoiceParser):
    """
    Table-aware invoice parser with column detection.

    Features:
    - Automatic column detection from headers
    - Multi-line description handling
    - Vertical block layout support
    - Position-based cell extraction
    """

    @property
    def name(self) -> str:
        return "table_aware"

    @property
    def priority(self) -> int:
        return 80

    def can_parse(self, text: str, hints: dict[str, Any] | None = None) -> float:
        """
        Check if text has table-like structure.

        Returns confidence based on:
        - Presence of header keywords
        - Aligned numeric columns
        - Multiple rows with similar structure
        """
        lines = text.split("\n")

        # Check for header row
        header_score = 0.0
        for line in lines[:30]:
            matches = sum(
                1
                for patterns in HEADER_PATTERNS.values()
                if any(p in line.lower() for p in patterns)
            )
            if matches >= 3:
                header_score = 0.7
                break

        # Check for aligned numbers (prices)
        price_pattern = re.compile(r"[\d,]+\.\d{2}")
        aligned_rows = 0
        for line in lines:
            if len(price_pattern.findall(line)) >= 2:
                aligned_rows += 1

        alignment_score = min(0.3, aligned_rows * 0.05)

        return header_score + alignment_score

    async def parse(
        self,
        text: str,
        filename: str,
        hints: dict[str, Any] | None = None,
    ) -> ParserResult:
        """Parse invoice using table-aware logic."""
        hints = hints or {}

        # Extract table block
        text = extract_table_block(text)
        lines = text.split("\n")

        # Check for vertical block layout
        if self._detect_vertical_layout(lines):
            items = self._parse_vertical_layout(lines)
            if items:
                return ParserResult(
                    success=True,
                    invoice=Invoice(items=items),
                    items=items,
                    confidence=0.8,
                    parser_name=self.name,
                    metadata={"layout": "vertical"},
                )

        # Find header row
        header_idx, column_map = self._find_header(lines, hints)

        if header_idx < 0:
            return ParserResult(
                success=False,
                parser_name=self.name,
                error="No header row detected",
            )

        # Parse items
        items = self._parse_items(lines, header_idx, column_map)

        if not items:
            return ParserResult(
                success=False,
                parser_name=self.name,
                error="No items extracted",
            )

        invoice = Invoice(items=items)
        invoice.total_quantity = sum(i.quantity for i in items if i.row_type == RowType.LINE_ITEM)

        return ParserResult(
            success=True,
            invoice=invoice,
            items=items,
            confidence=0.75,
            parser_name=self.name,
            metadata={"header_row": header_idx, "columns": list(column_map.keys())},
        )

    def _detect_vertical_layout(self, lines: list[str]) -> bool:
        """Detect if invoice uses vertical block layout."""
        numbered_lines = 0
        hs_lines = 0

        for line in lines[:100]:
            stripped = line.strip()
            if re.match(r"^\d+\s*[-–.]\s+", stripped):
                numbered_lines += 1
            if re.search(r"\b\d{8}\b", stripped):
                if re.search(r"\b(pcs?|pieces?|rolls?|meters?|m|kg)\b", stripped, re.IGNORECASE):
                    hs_lines += 1

        return numbered_lines >= 3 and hs_lines >= 3

    def _parse_vertical_layout(self, lines: list[str]) -> list[LineItem]:
        """Parse items from vertical block layout."""
        items = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Look for item start
            match = re.match(r"^(\d+)\s*[-–.]\s+(.+)", line)
            if not match:
                i += 1
                continue

            item_number = int(match.group(1))
            description_parts = [match.group(2).strip()]
            i += 1

            # Collect description until HS line
            while i < len(lines):
                next_line = lines[i].strip()

                # HS code line found
                hs_match = re.search(r"\b(\d{8})\b", next_line)
                if hs_match:
                    break

                # New item
                if re.match(r"^\d+\s*[-–.]\s+", next_line):
                    break

                if next_line:
                    description_parts.append(next_line)
                i += 1

            # Extract data from HS line
            hs_code = None
            quantity = None
            unit = None
            unit_price = None
            total_price = None

            if i < len(lines):
                hs_line = lines[i].strip()
                hs_match = re.search(r"\b(\d{8})\b", hs_line)
                if hs_match:
                    hs_code = hs_match.group(1)

                    # Extract numbers after HS code
                    remaining = hs_line[hs_match.end() :]
                    numbers = re.findall(r"[\d,]+(?:\.\d+)?", remaining)

                    if len(numbers) >= 1:
                        quantity = parse_number(numbers[0])
                    if len(numbers) >= 2:
                        unit_price = parse_number(numbers[1])
                    if len(numbers) >= 3:
                        total_price = parse_number(numbers[2])

                    # Extract unit
                    unit_match = re.search(
                        r"\b(pcs?|pieces?|rolls?|meters?|m|kg|kgs?|sets?|pairs?)\b",
                        remaining,
                        re.IGNORECASE,
                    )
                    if unit_match:
                        unit = unit_match.group(1)

                    i += 1

                    # Continue collecting description after HS line
                    while i < len(lines):
                        next_line = lines[i].strip()
                        if re.match(r"^\d+\s*[-–.]\s+", next_line):
                            break
                        if re.search(r"\b\d{8}\b", next_line):
                            break
                        if next_line and not is_bank_line(next_line):
                            description_parts.append(next_line)
                        i += 1

            description = " ".join(description_parts).strip()

            if description and (hs_code or quantity or total_price):
                items.append(
                    LineItem(
                        line_number=item_number,
                        item_name=clean_item_name(description),
                        description=description,
                        hs_code=hs_code,
                        unit=unit,
                        quantity=quantity or 0.0,
                        unit_price=unit_price or 0.0,
                        total_price=total_price or 0.0,
                        row_type=RowType.LINE_ITEM,
                    )
                )

        return items

    def _find_header(
        self,
        lines: list[str],
        hints: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        """Find header row and build column map."""
        min_gap = hints.get("min_gap", 2)
        header_pattern = hints.get("header_row_pattern")

        # Try pattern-based detection first
        if header_pattern:
            for i, line in enumerate(lines[:50]):
                try:
                    if re.search(header_pattern, line, re.IGNORECASE):
                        cells = split_cells_by_whitespace(line, min_gap)
                        column_map = self._classify_cells(cells)
                        if len(column_map) >= 2:
                            return i, column_map
                except re.error:
                    pass

        # Keyword-based detection
        for i, line in enumerate(lines[:50]):
            lower = line.lower()
            matches = sum(
                1 for patterns in HEADER_PATTERNS.values() if any(p in lower for p in patterns)
            )

            if matches >= 3:
                cells = split_cells_by_whitespace(line, min_gap)
                column_map = self._classify_cells(cells)
                if len(column_map) >= 2:
                    return i, column_map

        return -1, {}

    def _classify_cells(self, cells: list[dict[str, Any]]) -> dict[str, Any]:
        """Classify header cells into column types."""
        column_map = {}

        for idx, cell in enumerate(cells):
            text = cell["text"].lower()

            for col_type, patterns in HEADER_PATTERNS.items():
                if any(p in text for p in patterns):
                    if col_type not in column_map:
                        column_map[col_type] = {
                            "start_pos": cell["start_pos"],
                            "end_pos": cell["end_pos"],
                            "index": idx,
                            "text": cell["text"],
                        }
                    break

        return column_map

    def _parse_items(
        self,
        lines: list[str],
        header_idx: int,
        column_map: dict[str, Any],
    ) -> list[LineItem]:
        """Parse items from lines after header."""
        items = []
        line_number = 1

        for i in range(header_idx + 1, len(lines)):
            line = lines[i].strip()

            if len(line) < 5:
                continue

            if is_bank_line(line):
                continue

            if is_summary_or_meta_line(line):
                continue

            # Extract cells
            cells = split_cells_by_whitespace(line)
            if len(cells) < 2:
                continue

            # Map cells to columns
            row_data = self._extract_row_data(cells, column_map)

            # Validate minimum data
            has_numeric = any(
                [
                    row_data.get("quantity"),
                    row_data.get("unit_price"),
                    row_data.get("total_price"),
                ]
            )

            if not has_numeric:
                continue

            description = row_data.get("description", "")
            if not description:
                # Use first cell as description
                description = cells[0]["text"] if cells else ""

            if is_summary_or_meta_line(description):
                continue

            items.append(
                LineItem(
                    line_number=line_number,
                    item_name=clean_item_name(description),
                    description=description,
                    hs_code=row_data.get("hs_code"),
                    unit=row_data.get("unit"),
                    quantity=row_data.get("quantity") or 0.0,
                    unit_price=row_data.get("unit_price") or 0.0,
                    total_price=row_data.get("total_price") or 0.0,
                    row_type=RowType.LINE_ITEM,
                )
            )
            line_number += 1

        return items

    def _extract_row_data(self, cells: list[dict[str, Any]], column_map: dict[str, Any]) -> dict[str, Any]:
        """Extract data from row cells using column map."""
        data: dict[str, Any] = {}
        used_cells = set()

        for col_type, col_info in column_map.items():
            # Find closest cell to column position
            best_cell = None
            best_distance = float("inf")

            for idx, cell in enumerate(cells):
                if idx in used_cells:
                    continue

                cell_center = (cell["start_pos"] + cell["end_pos"]) / 2
                col_center = (col_info["start_pos"] + col_info["end_pos"]) / 2
                distance = abs(cell_center - col_center)

                # Prefer numeric cells for numeric columns
                if col_type in ["quantity", "unit_price", "total_price"]:
                    if not re.search(r"\d", cell["text"]):
                        distance += 1000

                if distance < best_distance:
                    best_distance = distance
                    best_cell = (idx, cell)

            if best_cell and best_distance < 100:
                idx, cell = best_cell
                used_cells.add(idx)
                value = cell["text"]

                if col_type in ["quantity", "unit_price", "total_price"]:
                    data[col_type] = parse_number(value)
                elif col_type == "hs_code":
                    data[col_type] = extract_hs_code(value)
                else:
                    data[col_type] = value

        # Infer unit_price if missing
        if not data.get("unit_price"):
            qty = data.get("quantity")
            total = data.get("total_price")
            if qty and qty > 0 and total and total > 0:
                data["unit_price"] = total / qty

        return data


# Singleton
_table_parser: TableAwareParser | None = None


def get_table_aware_parser() -> TableAwareParser:
    """Get or create table-aware parser singleton."""
    global _table_parser
    if _table_parser is None:
        _table_parser = TableAwareParser()
    return _table_parser
