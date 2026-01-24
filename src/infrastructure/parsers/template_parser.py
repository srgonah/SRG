"""
Template-based invoice parser.

Matches invoices against company templates for structured extraction.
"""

import re
from pathlib import Path

import yaml

from src.config import get_logger, get_settings
from src.core.entities import Invoice, LineItem, RowType
from src.core.interfaces import IInvoiceParser, ITemplateDetector, ParserResult, TemplateMatch
from src.infrastructure.parsers.base import clean_item_name, is_hs_code, parse_number

logger = get_logger(__name__)


class TemplateDetector(ITemplateDetector):
    """
    Detects which company template matches an invoice.

    Uses regex patterns defined in template YAML files.
    """

    def __init__(self):
        self._templates: dict[str, dict] = {}
        self._detection_cache: dict[str, TemplateMatch | None] = {}

    def load_templates(self, template_dir: str) -> int:
        """Load templates from directory."""
        path = Path(template_dir)
        if not path.exists():
            logger.warning("template_dir_not_found", path=str(path))
            return 0

        count = 0
        for yaml_file in path.glob("*.yaml"):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if not data:
                    continue

                template_id = yaml_file.stem
                data["_id"] = template_id
                data["_path"] = str(yaml_file)
                self._templates[template_id] = data
                count += 1

            except Exception as e:
                logger.error("template_load_error", file=str(yaml_file), error=str(e))

        logger.info("templates_loaded", count=count, dir=str(path))
        return count

    def detect(self, text: str) -> TemplateMatch | None:
        """Detect which template matches the invoice."""
        if not self._templates:
            settings = get_settings()
            self.load_templates(str(settings.parser.template_dir))

        # Check cache (use hash of first 1000 chars)
        cache_key = str(hash(text[:1000]))
        if cache_key in self._detection_cache:
            return self._detection_cache[cache_key]

        best_match: TemplateMatch | None = None
        best_score = 0.0

        for template_id, template in self._templates.items():
            score = self._calculate_match_score(text, template)

            if score > best_score:
                best_score = score
                best_match = TemplateMatch(
                    template_id=template_id,
                    template_name=template.get("company_name", template_id),
                    confidence=score,
                    company_key=template.get("company_key", template_id),
                    parser_hints=template.get("parser_hints", {}),
                )

        settings = get_settings()
        if best_match and best_match.confidence >= settings.parser.template_min_confidence:
            self._detection_cache[cache_key] = best_match
            logger.info(
                "template_matched",
                template=best_match.template_id,
                confidence=best_match.confidence,
            )
            return best_match

        self._detection_cache[cache_key] = None
        return None

    def _calculate_match_score(self, text: str, template: dict) -> float:
        """Calculate match score for a template."""
        patterns = template.get("detection_patterns", [])
        if not patterns:
            return 0.0

        matches = 0
        total = len(patterns)

        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                    matches += 1
            except re.error:
                continue

        return matches / total if total > 0 else 0.0

    def get_template(self, template_id: str) -> dict | None:
        """Get template by ID."""
        return self._templates.get(template_id)

    def list_templates(self) -> list[dict]:
        """List all loaded templates."""
        return [
            {
                "id": t.get("_id"),
                "name": t.get("company_name"),
                "company_key": t.get("company_key"),
            }
            for t in self._templates.values()
        ]


class TemplateParser(IInvoiceParser):
    """
    Template-based invoice parser.

    Uses company-specific templates for structured extraction.
    """

    def __init__(self, detector: TemplateDetector | None = None):
        self._detector = detector or TemplateDetector()

    @property
    def name(self) -> str:
        return "template"

    @property
    def priority(self) -> int:
        return 100  # Highest priority

    def can_parse(self, text: str, hints: dict | None = None) -> float:
        """Check if a template matches this invoice."""
        match = self._detector.detect(text)
        return match.confidence if match else 0.0

    async def parse(
        self,
        text: str,
        filename: str,
        hints: dict | None = None,
    ) -> ParserResult:
        """Parse invoice using matched template."""
        # Detect template
        match = self._detector.detect(text)
        if not match:
            return ParserResult(
                success=False,
                parser_name=self.name,
                error="No matching template found",
            )

        template = self._detector.get_template(match.template_id)
        if not template:
            return ParserResult(
                success=False,
                parser_name=self.name,
                error=f"Template {match.template_id} not found",
            )

        try:
            # Extract invoice metadata
            invoice = await self._extract_metadata(text, template)
            invoice.template_id = match.template_id
            invoice.template_confidence = match.confidence
            invoice.company_key = match.company_key

            # Extract line items
            items = await self._extract_items(text, template)
            invoice.items = items

            # Calculate totals
            invoice.total_quantity = sum(
                i.quantity for i in items if i.row_type == RowType.LINE_ITEM
            )

            logger.info(
                "template_parse_complete",
                template=match.template_id,
                items=len(items),
            )

            return ParserResult(
                success=True,
                invoice=invoice,
                items=items,
                confidence=match.confidence,
                parser_name=self.name,
                metadata={"template_id": match.template_id},
            )

        except Exception as e:
            logger.error("template_parse_error", error=str(e))
            return ParserResult(
                success=False,
                parser_name=self.name,
                error=str(e),
            )

    async def _extract_metadata(self, text: str, template: dict) -> Invoice:
        """Extract invoice metadata using template patterns."""
        invoice = Invoice()

        patterns = template.get("field_patterns", {})

        # Extract each field
        for field, pattern in patterns.items():
            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1) if match.lastindex else match.group(0)
                    value = value.strip()

                    if field == "invoice_no":
                        invoice.invoice_no = value
                    elif field == "invoice_date":
                        invoice.invoice_date = value
                    elif field == "seller_name":
                        invoice.seller_name = value
                    elif field == "buyer_name":
                        invoice.buyer_name = value
                    elif field == "total_amount":
                        invoice.total_amount = parse_number(value) or 0.0
                    elif field == "currency":
                        invoice.currency = value

            except re.error:
                continue

        return invoice

    async def _extract_items(self, text: str, template: dict) -> list[LineItem]:
        """Extract line items using template patterns."""
        items = []

        item_pattern = template.get("item_pattern")
        if not item_pattern:
            return items

        try:
            for i, match in enumerate(re.finditer(item_pattern, text, re.MULTILINE)):
                groups = match.groupdict() if match.lastindex else {}

                item = LineItem(
                    line_number=i + 1,
                    item_name=clean_item_name(groups.get("description", "")),
                    description=groups.get("description", ""),
                    hs_code=groups.get("hs_code")
                    if is_hs_code(groups.get("hs_code", ""))
                    else None,
                    unit=groups.get("unit"),
                    quantity=parse_number(groups.get("quantity")) or 0.0,
                    unit_price=parse_number(groups.get("unit_price")) or 0.0,
                    total_price=parse_number(groups.get("total_price")) or 0.0,
                    row_type=RowType.LINE_ITEM,
                )

                if item.item_name:
                    items.append(item)

        except re.error as e:
            logger.error("item_pattern_error", error=str(e))

        return items


# Singletons
_template_detector: TemplateDetector | None = None
_template_parser: TemplateParser | None = None


def get_template_detector() -> TemplateDetector:
    """Get or create template detector singleton."""
    global _template_detector
    if _template_detector is None:
        _template_detector = TemplateDetector()
    return _template_detector


def get_template_parser() -> TemplateParser:
    """Get or create template parser singleton."""
    global _template_parser
    if _template_parser is None:
        _template_parser = TemplateParser(get_template_detector())
    return _template_parser
