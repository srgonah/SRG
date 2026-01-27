"""
Vision-based invoice parser.

Uses LLaVA/vision models for complex or scanned invoice extraction.
Includes Pydantic validation for LLM JSON responses.
"""

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from src.config import get_logger, get_settings
from src.core.entities import Invoice, LineItem, RowType
from src.core.interfaces import IInvoiceParser, ParserResult
from src.infrastructure.llm import get_vision_provider
from src.infrastructure.parsers.base import clean_item_name, parse_date, parse_number

logger = get_logger(__name__)


# ============================================================================
# Pydantic Models for LLM Response Validation
# ============================================================================

class VisionLineItem(BaseModel):
    """Pydantic model for validating LLM-extracted line items."""

    description: str = ""
    hs_code: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    total_price: float | None = None

    @field_validator("description", mode="before")
    @classmethod
    def coerce_description(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("hs_code", mode="before")
    @classmethod
    def validate_hs_code(cls, v: Any) -> str | None:
        if v is None or v == "":
            return None
        s = str(v).replace(".", "").replace(" ", "")
        # HS codes should be 6-10 digits
        if re.match(r"^\d{6,10}$", s):
            return s
        return None

    @field_validator("quantity", "unit_price", "total_price", mode="before")
    @classmethod
    def coerce_numeric(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        try:
            # Handle string numbers
            s = str(v).strip().replace(",", "")
            if s.lower() in {"none", "null", "n/a", ""}:
                return None
            return float(s)
        except (ValueError, TypeError):
            return None


class VisionInvoiceResponse(BaseModel):
    """Pydantic model for validating complete LLM invoice extraction."""

    invoice_no: str | None = None
    invoice_date: str | None = None
    seller_name: str | None = None
    buyer_name: str | None = None
    currency: str = "USD"
    total_amount: float | None = None
    subtotal: float | None = None
    tax_amount: float | None = None
    items: list[VisionLineItem] = Field(default_factory=list)

    @field_validator("invoice_no", "seller_name", "buyer_name", mode="before")
    @classmethod
    def coerce_string(cls, v: Any) -> str | None:
        if v is None or v == "":
            return None
        return str(v).strip()

    @field_validator("currency", mode="before")
    @classmethod
    def default_currency(cls, v: Any) -> str:
        if v is None or v == "":
            return "USD"
        return str(v).upper().strip()

    @field_validator("total_amount", "subtotal", "tax_amount", mode="before")
    @classmethod
    def coerce_numeric(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        try:
            s = str(v).strip().replace(",", "")
            if s.lower() in {"none", "null", "n/a", ""}:
                return None
            return float(s)
        except (ValueError, TypeError):
            return None

VISION_EXTRACTION_PROMPT = """You are an invoice data extraction system. Extract structured data from this invoice image.

OUTPUT FORMAT: Return ONLY a valid JSON object. No explanations, no markdown, no text before or after the JSON.

REQUIRED JSON SCHEMA:
{
  "invoice_no": "string or null - the invoice number/ID",
  "invoice_date": "string or null - date in any format",
  "seller_name": "string or null - company issuing the invoice",
  "buyer_name": "string or null - company receiving the invoice",
  "currency": "string - 3-letter ISO code, default USD",
  "total_amount": "number or null - grand total amount",
  "subtotal": "number or null - subtotal before tax",
  "tax_amount": "number or null - tax/VAT amount",
  "items": [
    {
      "description": "string - item/product description (REQUIRED)",
      "hs_code": "string or null - 6-10 digit HS/tariff code",
      "quantity": "number or null - quantity ordered",
      "unit": "string or null - unit of measure (PCS, KG, etc.)",
      "unit_price": "number or null - price per unit",
      "total_price": "number or null - line total"
    }
  ]
}

EXTRACTION RULES:
1. Extract ALL line items from the invoice table - do not skip any
2. Use null for missing/unreadable values, NOT empty strings
3. Numbers must be raw numeric values without currency symbols or commas
4. HS codes are customs tariff codes, typically 6-10 digits
5. If you cannot read a value clearly, use null
6. description is REQUIRED for each item - skip items without descriptions

CRITICAL: Return ONLY the JSON object. No other text allowed."""


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

            # Parse and validate JSON response
            validated_data, validation_errors = self._parse_json_response(response.text)

            if not validated_data:
                logger.warning(
                    "vision_json_validation_failed",
                    errors=validation_errors,
                    raw_response_preview=response.text[:300],
                    filename=filename,
                )
                return ParserResult(
                    success=False,
                    parser_name=self.name,
                    error=f"JSON validation failed: {'; '.join(validation_errors)}",
                    metadata={
                        "raw_response": response.text[:500],
                        "validation_errors": validation_errors,
                    },
                )

            # Build invoice and items from validated data
            invoice = self._build_invoice(validated_data)
            items = self._build_items(validated_data.items)
            invoice.items = items

            # Calculate confidence based on extraction quality
            confidence = self._calculate_extraction_confidence(invoice, items)

            logger.info(
                "vision_parse_complete",
                items_count=len(items),
                invoice_no=invoice.invoice_no,
                confidence=confidence,
                filename=filename,
            )

            return ParserResult(
                success=True,
                invoice=invoice,
                items=items,
                confidence=confidence,
                parser_name=self.name,
                metadata={
                    "vision_model": response.model,
                    "validation_warnings": validation_errors if validation_errors else None,
                },
            )

        except Exception as e:
            logger.error("vision_parse_error", error=str(e))
            return ParserResult(
                success=False,
                parser_name=self.name,
                error=str(e),
            )

    def _extract_json_string(self, text: str) -> str | None:
        """Extract JSON string from LLM response text."""
        text = text.strip()

        # Try direct parse first
        if text.startswith("{"):
            return text

        # Try to extract from code block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            return match.group(1).strip()

        # Try to find JSON object
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return match.group(0)

        return None

    def _parse_json_response(self, text: str) -> tuple[VisionInvoiceResponse | None, list[str]]:
        """
        Parse and validate JSON from vision model response.

        Returns:
            Tuple of (validated response, list of validation errors)
        """
        errors: list[str] = []

        # Extract JSON string
        json_str = self._extract_json_string(text)
        if not json_str:
            errors.append("No JSON object found in response")
            return None, errors

        # Parse JSON
        try:
            raw_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON syntax: {str(e)}")
            return None, errors

        # Validate with Pydantic
        try:
            validated = VisionInvoiceResponse.model_validate(raw_data)
            return validated, errors
        except ValidationError as e:
            for err in e.errors():
                field = ".".join(str(loc) for loc in err["loc"])
                errors.append(f"Validation error at '{field}': {err['msg']}")
            return None, errors

    def _build_invoice(self, data: VisionInvoiceResponse) -> Invoice:
        """Build Invoice entity from validated Pydantic model."""
        # Parse date if present
        parsed_date = parse_date(data.invoice_date) if data.invoice_date else None

        return Invoice(
            invoice_no=data.invoice_no,
            invoice_date=parsed_date or data.invoice_date,
            seller_name=data.seller_name,
            buyer_name=data.buyer_name,
            currency=data.currency,
            total_amount=data.total_amount or 0.0,
            subtotal=data.subtotal or 0.0,
            tax_amount=data.tax_amount or 0.0,
        )

    def _build_items(self, items_data: list[VisionLineItem]) -> list[LineItem]:
        """Build LineItem entities from validated Pydantic models."""
        items = []

        for i, item_data in enumerate(items_data):
            # Skip items without description
            if not item_data.description:
                continue

            items.append(
                LineItem(
                    line_number=i + 1,
                    item_name=clean_item_name(item_data.description),
                    description=item_data.description,
                    hs_code=item_data.hs_code,
                    unit=item_data.unit,
                    quantity=item_data.quantity or 0.0,
                    unit_price=item_data.unit_price or 0.0,
                    total_price=item_data.total_price or 0.0,
                    row_type=RowType.LINE_ITEM,
                )
            )

        return items

    def _calculate_extraction_confidence(
        self,
        invoice: Invoice,
        items: list[LineItem],
    ) -> float:
        """
        Calculate confidence score based on extraction completeness.

        Scoring:
        - Has invoice number: +0.15
        - Has invoice date: +0.10
        - Has seller name: +0.10
        - Has items: +0.15
        - Items have quantities: +0.15 (scaled by coverage)
        - Items have prices: +0.20 (scaled by coverage)
        - Has total amount: +0.15
        """
        score = 0.0

        if invoice.invoice_no:
            score += 0.15
        if invoice.invoice_date:
            score += 0.10
        if invoice.seller_name:
            score += 0.10
        if invoice.total_amount > 0:
            score += 0.15

        if items:
            score += 0.15

            # Calculate item quality metrics
            items_with_qty = sum(1 for i in items if i.quantity > 0)
            items_with_price = sum(1 for i in items if i.unit_price > 0 or i.total_price > 0)

            qty_ratio = items_with_qty / len(items)
            price_ratio = items_with_price / len(items)

            score += 0.15 * qty_ratio
            score += 0.20 * price_ratio

        return min(1.0, max(0.0, score))


# Singleton
_vision_parser: VisionParser | None = None


def get_vision_parser() -> VisionParser:
    """Get or create vision parser singleton."""
    global _vision_parser
    if _vision_parser is None:
        _vision_parser = VisionParser()
    return _vision_parser
