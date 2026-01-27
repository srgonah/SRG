"""
Audit Invoice Use Case.

Performs comprehensive invoice auditing.
"""

from dataclasses import dataclass

from src.application.dto.requests import AuditInvoiceRequest
from src.application.dto.responses import AuditFindingResponse, AuditResultResponse
from src.application.services import get_invoice_auditor_service
from src.config import get_logger
from src.core.entities.invoice import AuditResult, Invoice
from src.core.exceptions import InvoiceNotFoundError
from src.core.interfaces import IInvoiceStore
from src.core.services import InvoiceAuditorService

logger = get_logger(__name__)


@dataclass
class AuditResultDTO:
    """Audit result data transfer object."""

    audit_result: AuditResult
    invoice: Invoice


class AuditInvoiceUseCase:
    """
    Use case for auditing invoices.

    Performs rule-based and LLM-powered analysis
    to detect errors and anomalies.
    """

    def __init__(
        self,
        auditor_service: InvoiceAuditorService | None = None,
        invoice_store: IInvoiceStore | None = None,
    ):
        """
        Initialize use case with optional service overrides.

        Args:
            auditor_service: Invoice auditor service
            invoice_store: Invoice persistence store
        """
        self._auditor = auditor_service
        self._invoice_store = invoice_store

    def _get_auditor(self) -> InvoiceAuditorService:
        if self._auditor is None:
            self._auditor = get_invoice_auditor_service()
        return self._auditor

    async def _get_invoice_store(self) -> IInvoiceStore:
        if self._invoice_store is None:
            # Lazy import to avoid circular imports
            from src.infrastructure.storage.sqlite import get_invoice_store
            self._invoice_store = await get_invoice_store()
        return self._invoice_store

    async def execute(self, request: AuditInvoiceRequest) -> AuditResultDTO:
        """
        Execute audit use case.

        Args:
            request: Audit request with invoice ID and options

        Returns:
            AuditResultDTO with audit result and invoice

        Raises:
            InvoiceNotFoundError: If invoice not found
        """
        logger.info("audit_invoice_started", invoice_id=request.invoice_id)

        # Get invoice
        store = await self._get_invoice_store()
        invoice = await store.get_invoice(request.invoice_id)  # type: ignore[arg-type]

        if not invoice:
            # Convert string ID to int for exception, handle gracefully
            try:
                inv_id = int(request.invoice_id)
            except ValueError:
                inv_id = 0  # Fallback for non-numeric IDs
            raise InvoiceNotFoundError(inv_id)

        # Perform audit
        auditor = self._get_auditor()
        audit_result = await auditor.audit_invoice(
            invoice=invoice,
            use_llm=request.use_llm,
        )

        # Save audit result
        await store.save_audit_result(audit_result)  # type: ignore[attr-defined]

        logger.info(
            "audit_invoice_complete",
            invoice_id=request.invoice_id,
            passed=audit_result.passed,
            findings=len(audit_result.issues),
        )

        return AuditResultDTO(
            audit_result=audit_result,
            invoice=invoice,
        )

    async def get_latest_audit(self, invoice_id: str) -> AuditResult | None:
        """Get the most recent audit result for an invoice."""
        store = await self._get_invoice_store()
        results = await store.list_audit_results(invoice_id=int(invoice_id), limit=1)
        return results[0] if results else None

    async def get_audit_history(
        self,
        invoice_id: str,
        limit: int = 10,
    ) -> list[AuditResult]:
        """Get audit history for an invoice."""
        store = await self._get_invoice_store()
        return await store.list_audit_results(invoice_id=int(invoice_id), limit=limit)

    def to_response(self, result: AuditResultDTO) -> AuditResultResponse:
        """Convert to API response format."""
        ar = result.audit_result

        return AuditResultResponse(
            id=str(ar.id) if ar.id is not None else "0",
            invoice_id=str(ar.invoice_id),
            passed=ar.passed,
            confidence=ar.confidence,
            findings=[
                AuditFindingResponse(
                    code=f.code,
                    category=f.category,
                    severity=f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                    message=f.message,
                    field=f.field,
                    expected=f.expected,
                    actual=f.actual,
                )
                for f in ar.issues
            ],
            audited_at=ar.audited_at or ar.created_at,
            error_count=sum(1 for f in ar.issues if f.severity.value == "error"),
            warning_count=sum(1 for f in ar.issues if f.severity.value == "warning"),
        )
