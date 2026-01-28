"""
Proforma PDF generation service.

Pure service that orchestrates PDF generation from invoice and audit data.
The actual rendering is delegated to an injected IProformaPdfRenderer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.config import get_logger
from src.core.entities.invoice import AuditResult, Invoice
from src.core.interfaces.storage import IInvoiceStore

logger = get_logger(__name__)


class IProformaPdfRenderer(ABC):
    """Interface for PDF rendering implementations."""

    @abstractmethod
    def render(self, invoice: Invoice, audit: AuditResult) -> bytes:
        """Render invoice and audit data into PDF bytes."""
        pass


@dataclass
class ProformaPdfResult:
    """Result of proforma PDF generation."""

    pdf_bytes: bytes
    invoice_id: int
    file_path: str
    file_size: int


class ProformaPdfService:
    """
    Service for generating proforma PDFs from invoice + audit data.

    Loads data from stores, delegates rendering to IProformaPdfRenderer,
    and returns the generated PDF bytes.
    """

    def __init__(
        self,
        renderer: IProformaPdfRenderer,
        invoice_store: IInvoiceStore,
    ):
        self._renderer = renderer
        self._invoice_store = invoice_store

    async def generate_proforma_pdf(self, invoice_id: int) -> ProformaPdfResult:
        """
        Generate a proforma PDF for the given invoice.

        Args:
            invoice_id: The ID of the invoice to generate a PDF for.

        Returns:
            ProformaPdfResult with PDF bytes and metadata.

        Raises:
            ValueError: If invoice or audit result not found.
        """
        # Load invoice
        invoice = await self._invoice_store.get_invoice(invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice not found: {invoice_id}")

        # Load audit result
        audit = await self._invoice_store.get_audit_result(invoice_id)
        if audit is None:
            raise ValueError(f"Audit result not found for invoice: {invoice_id}")

        # Render PDF
        logger.info("generating_proforma_pdf", invoice_id=invoice_id)
        pdf_bytes = self._renderer.render(invoice, audit)

        file_path = f"proforma_{invoice_id}.pdf"

        logger.info(
            "proforma_pdf_generated",
            invoice_id=invoice_id,
            size_bytes=len(pdf_bytes),
        )

        return ProformaPdfResult(
            pdf_bytes=pdf_bytes,
            invoice_id=invoice_id,
            file_path=file_path,
            file_size=len(pdf_bytes),
        )
