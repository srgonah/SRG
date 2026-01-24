"""
Invoice parser orchestration service.

Coordinates multiple parsing strategies to extract invoice data.
"""

from pathlib import Path

from src.config import get_logger, get_settings
from src.core.entities.document import Document, Page
from src.core.entities.invoice import Invoice
from src.core.exceptions import ParserError
from src.infrastructure.parsers import ParserRegistry, get_parser_registry

logger = get_logger(__name__)


class InvoiceParserService:
    """
    Orchestrates invoice parsing using multiple strategies.

    Tries parsers in priority order until successful extraction.
    """

    def __init__(self, parser_registry: ParserRegistry | None = None):
        """
        Initialize parser service.

        Args:
            parser_registry: Optional custom parser registry
        """
        self._registry = parser_registry or get_parser_registry()
        self._settings = get_settings()

    async def parse_invoice(
        self,
        document: Document,
        pages: list[Page],
    ) -> Invoice:
        """
        Parse invoice from document pages.

        Tries parsers in priority order until one succeeds.

        Args:
            document: Document entity
            pages: List of page entities with extracted text

        Returns:
            Parsed Invoice entity

        Raises:
            ParserError: If all parsers fail
        """
        if not pages:
            raise ParserError("No pages to parse")

        # Combine page texts
        full_text = "\n\n".join(
            f"--- Page {p.page_number} ---\n{p.text_content}" for p in pages if p.text_content
        )

        if not full_text.strip():
            raise ParserError("No text content in document")

        logger.info(
            "parsing_invoice",
            document_id=document.id,
            page_count=len(pages),
            text_length=len(full_text),
        )

        errors = []

        # Try each parser in priority order
        for parser in self._registry.get_parsers_by_priority():
            parser_name = parser.__class__.__name__

            try:
                logger.debug("trying_parser", parser=parser_name)

                invoice = await parser.parse(full_text, document.file_path)

                if invoice and invoice.line_items:
                    logger.info(
                        "parsing_success",
                        parser=parser_name,
                        items=len(invoice.line_items),
                        total=invoice.calculated_total,
                    )

                    # Update invoice with document reference
                    invoice.document_id = document.id
                    invoice.source_file = document.file_path

                    return invoice

                logger.debug(
                    "parser_no_results",
                    parser=parser_name,
                )

            except Exception as e:
                logger.warning(
                    "parser_failed",
                    parser=parser_name,
                    error=str(e),
                )
                errors.append(f"{parser_name}: {str(e)}")

        # All parsers failed
        raise ParserError(f"All parsers failed for {document.file_path}: {'; '.join(errors)}")

    async def parse_from_file(self, file_path: str) -> Invoice:
        """
        Parse invoice directly from file path.

        Convenience method that extracts text and parses.

        Args:
            file_path: Path to invoice file

        Returns:
            Parsed Invoice entity
        """
        import fitz  # PyMuPDF

        path = Path(file_path)
        if not path.exists():
            raise ParserError(f"File not found: {file_path}")

        # Create temporary document
        document = Document(
            file_path=str(path),
            file_name=path.name,
            file_type=path.suffix.lower(),
            file_size=path.stat().st_size,
        )

        # Extract pages
        pages = []

        if path.suffix.lower() == ".pdf":
            doc = fitz.open(str(path))
            try:
                for i, page in enumerate(doc):
                    text = page.get_text()
                    pages.append(
                        Page(
                            document_id=document.id,
                            page_number=i + 1,
                            text_content=text,
                            width=page.rect.width,
                            height=page.rect.height,
                        )
                    )
            finally:
                doc.close()
        else:
            # Try reading as text file
            try:
                text = path.read_text(encoding="utf-8")
                pages.append(
                    Page(
                        document_id=document.id,
                        page_number=1,
                        text_content=text,
                    )
                )
            except Exception as e:
                raise ParserError(f"Cannot read file: {e}")

        return await self.parse_invoice(document, pages)

    async def validate_invoice(self, invoice: Invoice) -> list[str]:
        """
        Validate parsed invoice for common issues.

        Args:
            invoice: Invoice to validate

        Returns:
            List of validation warnings
        """
        warnings = []

        # Check for missing required fields
        if not invoice.invoice_number:
            warnings.append("Missing invoice number")

        if not invoice.vendor_name:
            warnings.append("Missing vendor name")

        if not invoice.invoice_date:
            warnings.append("Missing invoice date")

        # Check line items
        if not invoice.line_items:
            warnings.append("No line items found")
        else:
            for i, item in enumerate(invoice.line_items):
                if not item.description:
                    warnings.append(f"Line {i + 1}: Missing description")

                if item.quantity <= 0:
                    warnings.append(f"Line {i + 1}: Invalid quantity")

                if item.unit_price <= 0:
                    warnings.append(f"Line {i + 1}: Invalid unit price")

                # Check total calculation
                expected = round(item.quantity * item.unit_price, 2)
                if abs(item.total_price - expected) > 0.01:
                    warnings.append(
                        f"Line {i + 1}: Total mismatch "
                        f"(got {item.total_price}, expected {expected})"
                    )

        # Check document total
        if invoice.total_amount:
            diff = abs(invoice.total_amount - invoice.calculated_total)
            if diff > 0.01:
                warnings.append(
                    f"Document total {invoice.total_amount} != "
                    f"calculated {invoice.calculated_total}"
                )

        return warnings


# Singleton
_parser_service: InvoiceParserService | None = None


def get_invoice_parser_service() -> InvoiceParserService:
    """Get or create invoice parser service singleton."""
    global _parser_service
    if _parser_service is None:
        _parser_service = InvoiceParserService()
    return _parser_service
