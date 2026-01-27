"""
Upload Invoice Use Case.

Handles invoice upload, parsing, and optional auditing.
"""

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.application.dto.requests import UploadInvoiceRequest
from src.application.dto.responses import AuditResultResponse, InvoiceResponse
from src.application.services import (
    get_document_indexer_service,
    get_invoice_auditor_service,
    get_invoice_parser_service,
)
from src.config import get_logger
from src.core.entities.document import Document
from src.core.entities.invoice import AuditResult, Invoice
from src.core.interfaces import IDocumentStore, IInvoiceStore
from src.core.services import (
    DocumentIndexerService,
    InvoiceAuditorService,
    InvoiceParserService,
)

logger = get_logger(__name__)


@dataclass
class UploadResult:
    """Result of invoice upload."""

    invoice: Invoice
    document: Document
    audit_result: AuditResult | None = None
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.warnings:
            self.warnings = []


class UploadInvoiceUseCase:
    """
    Use case for uploading and processing invoices.

    Flow:
    1. Save uploaded file
    2. Extract text from PDF
    3. Parse invoice using parser service
    4. Store invoice in database
    5. Optionally audit invoice
    6. Index document for search
    """

    def __init__(
        self,
        parser_service: InvoiceParserService | None = None,
        auditor_service: InvoiceAuditorService | None = None,
        indexer_service: DocumentIndexerService | None = None,
        invoice_store: IInvoiceStore | None = None,
        document_store: IDocumentStore | None = None,
    ):
        """
        Initialize use case with optional service overrides.

        All dependencies are lazily initialized if not provided.
        This enables both production use and testing with mocks.

        Args:
            parser_service: Invoice parser service
            auditor_service: Invoice auditor service
            indexer_service: Document indexer service
            invoice_store: Invoice persistence store
            document_store: Document persistence store
        """
        self._parser = parser_service
        self._auditor = auditor_service
        self._indexer = indexer_service
        self._invoice_store = invoice_store
        self._document_store = document_store

    def _get_parser(self) -> InvoiceParserService:
        if self._parser is None:
            self._parser = get_invoice_parser_service()
        return self._parser

    def _get_auditor(self) -> InvoiceAuditorService:
        if self._auditor is None:
            self._auditor = get_invoice_auditor_service()
        return self._auditor

    async def _get_indexer(self) -> DocumentIndexerService:
        if self._indexer is None:
            self._indexer = await get_document_indexer_service()
        return self._indexer

    async def _get_invoice_store(self) -> IInvoiceStore:
        if self._invoice_store is None:
            # Lazy import to avoid circular imports
            from src.infrastructure.storage.sqlite import get_invoice_store
            self._invoice_store = await get_invoice_store()
        return self._invoice_store

    async def _get_document_store(self) -> IDocumentStore:
        if self._document_store is None:
            # Lazy import to avoid circular imports
            from src.infrastructure.storage.sqlite import get_document_store
            self._document_store = await get_document_store()
        return self._document_store

    async def execute(
        self,
        file_content: bytes,
        filename: str,
        request: UploadInvoiceRequest,
    ) -> UploadResult:
        """
        Execute invoice upload use case.

        Args:
            file_content: Raw file bytes
            filename: Original filename
            request: Upload request parameters

        Returns:
            UploadResult with invoice, document, and optional audit
        """
        logger.info("upload_invoice_started", filename=filename)

        # Save file temporarily
        temp_dir = Path(tempfile.mkdtemp())
        try:
            file_path = temp_dir / filename
            file_path.write_bytes(file_content)

            # Index document (extracts text, creates chunks)
            indexer = await self._get_indexer()
            document = await indexer.index_document(  # type: ignore[call-arg]
                str(file_path),  # type: ignore[arg-type]
                metadata={
                    "vendor_hint": request.vendor_hint,
                    "template_id": request.template_id,
                },
            )

            # Get pages for parsing
            doc_store = await self._get_document_store()
            pages = await doc_store.get_pages_by_document(document.id)  # type: ignore[attr-defined]

            # Parse invoice
            parser = self._get_parser()
            invoice = await parser.parse_invoice(document, pages)  # type: ignore[arg-type]

            # Validate
            warnings = parser.validate_invoice(invoice)  # type: ignore[arg-type]

            # Store invoice
            inv_store = await self._get_invoice_store()
            await inv_store.save_invoice(invoice)  # type: ignore[attr-defined]

            # Optional audit
            audit_result = None
            if request.auto_audit:
                auditor = self._get_auditor()
                audit_result = await auditor.audit_invoice(invoice)  # type: ignore[arg-type]
                await inv_store.save_audit_result(audit_result)  # type: ignore[attr-defined]

            logger.info(
                "upload_invoice_complete",
                invoice_id=invoice.id,  # type: ignore[attr-defined]
                items=len(invoice.items or []),
                audited=audit_result is not None,
            )

            return UploadResult(
                invoice=invoice,  # type: ignore[arg-type]
                document=document,  # type: ignore[arg-type]
                audit_result=audit_result,
                warnings=warnings,
            )

        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def upload_from_path(
        self,
        file_path: str,
        auto_audit: bool = True,
    ) -> UploadResult:
        """
        Upload invoice from file path.

        Convenience method for local files.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = path.read_bytes()
        request = UploadInvoiceRequest(auto_audit=auto_audit)

        return await self.execute(content, path.name, request)

    def to_response(self, result: UploadResult) -> dict[str, Any]:
        """Convert result to API response format."""
        invoice = result.invoice

        response: dict[str, Any] = {
            "invoice": InvoiceResponse(
                id=str(invoice.id) if invoice.id else "0",
                document_id=str(invoice.doc_id) if invoice.doc_id else None,
                invoice_number=invoice.invoice_no,
                vendor_name=invoice.seller_name,
                vendor_address=None,  # Not in entity
                invoice_date=invoice.invoice_date,
                due_date=invoice.due_date,
                subtotal=invoice.subtotal,
                tax_amount=invoice.tax_amount,
                total_amount=invoice.total_amount,
                currency=invoice.currency,
                line_items=[
                    {  # type: ignore[misc]
                        "description": item.description or item.item_name,
                        "quantity": item.quantity,
                        "unit": item.unit,
                        "unit_price": item.unit_price,
                        "total_price": item.total_price,
                        "reference": getattr(item, "reference", None),
                    }
                    for item in invoice.items
                ],
                calculated_total=invoice.calculated_total,
                source_file=None,  # Not in entity
                parsed_at=invoice.created_at,  # Use created_at instead
                confidence=invoice.confidence,
            ),
            "document_id": result.document.id,
            "warnings": result.warnings,
        }

        if result.audit_result:
            ar = result.audit_result
            response["audit"] = AuditResultResponse(
                id=str(ar.id) if ar.id else "0",
                invoice_id=str(ar.invoice_id),
                passed=ar.passed,
                confidence=ar.confidence,
                findings=[
                    {  # type: ignore[misc]
                        "code": issue.code,
                        "category": issue.category,
                        "severity": issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity),
                        "message": issue.message,
                        "field": issue.field,
                        "expected": issue.expected,
                        "actual": issue.actual,
                    }
                    for issue in ar.issues
                ],
                audited_at=ar.audited_at or ar.created_at,
                error_count=ar.errors_count,
                warning_count=ar.warnings_count,
            )
        else:
            response["audit"] = None

        return response
