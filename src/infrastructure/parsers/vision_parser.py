"""
Vision-based invoice parser.

Uses LLaVA/vision models for complex or scanned invoice extraction.
"""

import json
import re

from src.config import get_logger, get_settings
from src.core.entities import Invoice, LineItem, RowType
from src.core.interfaces import IInvoiceParser, ParserResult
from src.infrastructure.llm import get_vision_provider
from src.infrastructure.parsers.base import clean_item_name, parse_number

logger = get_logger(__name__)

VISION_EXTRACTION_PROMPT = """Extract invoice data from this image as JSON.

Return a JSON object with these fields:
{
  "invoice_no": "string or null",
  "invoice_date": "string or null",
  "seller_name": "string or null",
  "buyer_name": "string or null",
  "currency": "string, default USD",
  "total_amount": number or null,
  "items": [
    {
      "description": "item description",
      "hs_code": "6-10 digit code or null",
      "quantity": number,
      "unit": "unit of measure or null",
      "unit_price": number,
      "total_price": number
    }
  ]
}

Rules:
- Extract ALL line items from the invoice table
- Use null for missing values, not empty strings
- Numbers should be raw values without currency symbols
- HS codes are typically 6-10 digits

Return ONLY valid JSON, no explanations."""


class VisionParser(IInvoiceParser):
    """
    Vision-based invoice parser using LLaVA.

    Used as fallback for complex or scanned invoices.
    """

    @property
    def name(self) -> str:
        return "vision"

    @property
    def priority(self) -> int:
        return 60  # Lower priority - used as fallback

    def can_parse(self, text: str, hints: dict | None = None) -> float:
        """
        Check if vision parsing should be attempted.

        Returns high confidence if:
        - Text extraction quality is low
        - Hints indicate vision is preferred
        - Text has OCR artifacts
        """
        if hints and hints.get("prefer_vision"):
            return 0.9

        if hints and hints.get("image_path"):
            # Has image available
            return 0.6

        # Check for OCR quality issues
        if self._has_ocr_artifacts(text):
            return 0.7

        return 0.0

    def _has_ocr_artifacts(self, text: str) -> bool:
        """Check if text shows signs of poor OCR quality."""
        if not text:
            return True

        # Very short text
        if len(text) < 100:
            return True

        # High ratio of non-alphanumeric characters
        alpha_num = sum(1 for c in text if c.isalnum())
        if len(text) > 0 and alpha_num / len(text) < 0.5:
            return True

        # Too many consecutive special characters
        if re.search(r"[^\w\s]{5,}", text):
            return True

        return False

    async def parse(
        self,
        text: str,
        filename: str,
        hints: dict | None = None,
    ) -> ParserResult:
        """Parse invoice using vision model."""
        hints = hints or {}
        image_path = hints.get("image_path")

        if not image_path:
            return ParserResult(
                success=False,
                parser_name=self.name,
                error="No image path provided for vision parsing",
            )

        settings = get_settings()
        if not settings.parser.vision_enabled:
            return ParserResult(
                success=False,
                parser_name=self.name,
                error="Vision parsing is disabled",
            )

        try:
            # Get vision provider
            vision = get_vision_provider()

            # Analyze image
            response = await vision.analyze_image(
                image_path,
                VISION_EXTRACTION_PROMPT,
                max_tokens=4096,
            )

            if response.error:
                return ParserResult(
                    success=False,
                    parser_name=self.name,
                    error=f"Vision model error: {response.error}",
                )

            # Parse JSON response
            data = self._parse_json_response(response.text)
            if not data:
                return ParserResult(
                    success=False,
                    parser_name=self.name,
                    error="Failed to parse vision model response as JSON",
                    metadata={"raw_response": response.text[:500]},
                )

            # Build invoice and items
            invoice = self._build_invoice(data)
            items = self._build_items(data.get("items", []))
            invoice.items = items

            logger.info(
                "vision_parse_complete",
                items=len(items),
                invoice_no=invoice.invoice_no,
            )

            return ParserResult(
                success=True,
                invoice=invoice,
                items=items,
                confidence=settings.parser.vision_min_confidence,
                parser_name=self.name,
                metadata={"vision_model": response.model},
            )

        except Exception as e:
            logger.error("vision_parse_error", error=str(e))
            return ParserResult(
                success=False,
                parser_name=self.name,
                error=str(e),
            )

    def _parse_json_response(self, text: str) -> dict | None:
        """Parse JSON from vision model response."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract from code block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try to find JSON object
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def _build_invoice(self, data: dict) -> Invoice:
        """Build Invoice entity from parsed data."""
        return Invoice(
            invoice_no=data.get("invoice_no"),
            invoice_date=data.get("invoice_date"),
            seller_name=data.get("seller_name"),
            buyer_name=data.get("buyer_name"),
            currency=data.get("currency", "USD"),
            total_amount=parse_number(str(data.get("total_amount"))) or 0.0,
        )

    def _build_items(self, items_data: list) -> list[LineItem]:
        """Build LineItem entities from parsed data."""
        items = []

        for i, item_data in enumerate(items_data):
            description = item_data.get("description", "")
            if not description:
                continue

            items.append(
                LineItem(
                    line_number=i + 1,
                    item_name=clean_item_name(description),
                    description=description,
                    hs_code=item_data.get("hs_code"),
                    unit=item_data.get("unit"),
                    quantity=parse_number(str(item_data.get("quantity"))) or 0.0,
                    unit_price=parse_number(str(item_data.get("unit_price"))) or 0.0,
                    total_price=parse_number(str(item_data.get("total_price"))) or 0.0,
                    row_type=RowType.LINE_ITEM,
                )
            )

        return items


# Singleton
_vision_parser: VisionParser | None = None


def get_vision_parser() -> VisionParser:
    """Get or create vision parser singleton."""
    global _vision_parser
    if _vision_parser is None:
        _vision_parser = VisionParser()
    return _vision_parser
