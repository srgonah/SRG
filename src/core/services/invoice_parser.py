"""
Invoice parser orchestration service.

Layer-pure service that coordinates parsing via injected interfaces.
NO infrastructure imports - depends only on core entities, interfaces, exceptions.
"""

from typing import Any

from src.core.entities.document import Document, Page
from src.core.entities.invoice import Invoice, LineItem
from src.core.exceptions import ParserError
from src.core.interfaces import (
    IDocumentStore,
    IInvoiceStore,
    IParserRegistry,
    ParserResult,
)


class InvoiceParserService:
    """
    Orchestrates invoice parsing using the parser registry.

    Coordinates multiple parsing strategies and stores results.
    All dependencies are injected via constructor.

    Required interfaces for DI:
    - IParserRegistry: Parser strategy orchestration
    - IDocumentStore: Document persistence (optional)
    - IInvoiceStore: Invoice persistence (optional)
    """

    def __init__(
        self,
        parser_registry: IParserRegistry,
        document_store: IDocumentStore | None = None,
        invoice_store: IInvoiceStore | None = None,
    ):
        """
        Initialize parser service with injected dependencies.

        Args:
            parser_registry: Registry of parser strategies
            document_store: Optional document persistence
            invoice_store: Optional invoice persistence
        """
        self._registry = parser_registry
        self._doc_store = document_store
        self._invoice_store = invoice_store

    async def parse_invoice(
        self,
        text: str,
        filename: str,
        hints: dict[str, Any] | None = None,
        save_result: bool = True,
    ) -> ParserResult:
        """
        Parse invoice text using the parser registry.

        Args:
            text: Extracted text content
            filename: Original filename for context
            hints: Optional parsing hints (image_path, prefer_vision, etc.)
            save_result: Whether to save to invoice store

        Returns:
            ParserResult with invoice data and metadata

        Raises:
            ParserError: If parsing fails completely
        """
        if not text or not text.strip():
            raise ParserError("No text content to parse")

        # Delegate to parser registry
        result = await self._registry.parse(text, filename, hints or {})

        if not result.success:
            raise ParserError(result.error or "All parsers failed")

        # Optionally persist the invoice
        if save_result and result.invoice and self._invoice_store:
            result.invoice = await self._invoice_store.create_invoice(result.invoice)

        return result

    async def parse_document(
        self,
        document: Document,
        pages: list[Page],
        hints: dict[str, Any] | None = None,
    ) -> ParserResult:
        """
        Parse invoice from a document and its pages.

        Args:
            document: Document entity
            pages: List of pages with extracted text
            hints: Optional parsing hints

        Returns:
            ParserResult with invoice data

        Raises:
            ParserError: If no pages or parsing fails
        """
        if not pages:
            raise ParserError("No pages to parse")

        # Combine page texts with page markers
        full_text = "\n\n".join(
            f"--- Page {p.page_no} ---\n{p.text}"
            for p in pages
            if p.text
        )

        if not full_text.strip():
            raise ParserError("No text content in document pages")

        # Add document context to hints
        hints = hints or {}
        hints["doc_id"] = document.id
        hints["filename"] = document.filename

        result = await self.parse_invoice(full_text, document.filename, hints)

        # Link invoice to document
        if result.success and result.invoice:
            result.invoice.doc_id = document.id

        return result

    async def parse_with_parser(
        self,
        parser_name: str,
        text: str,
        filename: str,
        hints: dict[str, Any] | None = None,
    ) -> ParserResult:
        """
        Parse using a specific parser by name.

        Useful for testing or when a specific strategy is required.

        Args:
            parser_name: Name of parser to use
            text: Text content to parse
            filename: Original filename
            hints: Optional parsing hints

        Returns:
            ParserResult from specified parser
        """
        return await self._registry.parse_with_parser(
            parser_name, text, filename, hints or {}
        )

    def validate_invoice(self, invoice: Invoice) -> list[str]:
        """
        Validate parsed invoice for common issues.

        Pure validation logic - no infrastructure dependencies.

        Args:
            invoice: Invoice to validate

        Returns:
            List of validation warnings
        """
        warnings = []

        # Required fields
        if not invoice.invoice_no:
            warnings.append("Missing invoice number")

        if not invoice.seller_name:
            warnings.append("Missing seller name")

        if not invoice.invoice_date:
            warnings.append("Missing invoice date")

        # Line items
        if not invoice.items:
            warnings.append("No line items found")
        else:
            for i, item in enumerate(invoice.items, 1):
                item_warnings = self._validate_line_item(item, i)
                warnings.extend(item_warnings)

        # Total consistency
        if invoice.total_amount and invoice.items:
            calculated = sum(item.total_price for item in invoice.items)
            diff = abs(invoice.total_amount - calculated)
            if diff > 0.02:
                warnings.append(
                    f"Total mismatch: declared {invoice.total_amount} vs "
                    f"calculated {calculated:.2f}"
                )

        return warnings

    def _validate_line_item(self, item: LineItem, line_no: int) -> list[str]:
        """Validate a single line item."""
        warnings = []

        if not item.item_name:
            warnings.append(f"Line {line_no}: Missing description")

        if item.quantity <= 0:
            warnings.append(f"Line {line_no}: Invalid quantity ({item.quantity})")

        if item.unit_price < 0:
            warnings.append(f"Line {line_no}: Negative unit price ({item.unit_price})")

        # Check line total calculation
        expected = round(item.quantity * item.unit_price, 2)
        if abs(item.total_price - expected) > 0.01:
            warnings.append(
                f"Line {line_no}: Total mismatch "
                f"(got {item.total_price}, expected {expected})"
            )

        return warnings

    def get_available_parsers(self) -> list[str]:
        """Get names of all registered parsers."""
        return [p.name for p in self._registry.get_parsers()]

    def get_parser_info(self) -> list[dict[str, Any]]:
        """Get info about all registered parsers."""
        return [
            {
                "name": p.name,
                "priority": p.priority,
            }
            for p in self._registry.get_parsers()
        ]
