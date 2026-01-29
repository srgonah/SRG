"""
Create Sales PDF Use Case.

Generates a PDF document from a local sales invoice.
"""

from dataclasses import dataclass

from src.application.dto.responses import SalesPdfResponse
from src.config import get_logger
from src.core.interfaces.sales_store import ISalesStore
from src.infrastructure.pdf.sales_pdf_renderer import Fpdf2SalesRenderer, ISalesPdfRenderer

logger = get_logger(__name__)


@dataclass
class SalesPdfResult:
    """Result of sales PDF generation."""

    pdf_bytes: bytes
    invoice_id: int
    file_path: str
    file_size: int


class CreateSalesPdfUseCase:
    """
    Use case for generating sales invoice PDFs.

    Flow:
    1. Load sales invoice from store
    2. Render PDF via SalesPdfRenderer
    3. Return PDF bytes and metadata
    """

    def __init__(
        self,
        sales_store: ISalesStore | None = None,
        renderer: ISalesPdfRenderer | None = None,
    ):
        self._sales_store = sales_store
        self._renderer = renderer or Fpdf2SalesRenderer()

    async def _get_sales_store(self) -> ISalesStore:
        if self._sales_store is None:
            from src.infrastructure.storage.sqlite import get_sales_store

            self._sales_store = await get_sales_store()
        return self._sales_store

    async def execute(self, invoice_id: int) -> SalesPdfResult:
        """
        Generate a sales invoice PDF.

        Args:
            invoice_id: The sales invoice ID.

        Returns:
            SalesPdfResult with PDF bytes and metadata.

        Raises:
            ValueError: If the sales invoice is not found.
        """
        logger.info("create_sales_pdf_started", invoice_id=invoice_id)

        store = await self._get_sales_store()
        invoice = await store.get_invoice(invoice_id)
        if invoice is None:
            raise ValueError(f"Sales invoice not found: {invoice_id}")

        pdf_bytes = self._renderer.render(invoice)
        file_path = f"sales_invoice_{invoice_id}.pdf"

        logger.info(
            "create_sales_pdf_complete",
            invoice_id=invoice_id,
            file_size=len(pdf_bytes),
        )

        return SalesPdfResult(
            pdf_bytes=pdf_bytes,
            invoice_id=invoice_id,
            file_path=file_path,
            file_size=len(pdf_bytes),
        )

    @staticmethod
    def to_response(result: SalesPdfResult) -> SalesPdfResponse:
        """Convert result to API response."""
        return SalesPdfResponse(
            invoice_id=result.invoice_id,
            file_path=result.file_path,
            file_size=result.file_size,
        )
