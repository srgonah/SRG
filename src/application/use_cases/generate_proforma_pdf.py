"""
Generate Proforma PDF Use Case.

Generates a proforma PDF document from an invoice and its audit result.
"""


from src.application.dto.responses import ProformaPdfResponse
from src.config import get_logger
from src.core.services.proforma_pdf_service import ProformaPdfResult, ProformaPdfService

logger = get_logger(__name__)


class GenerateProformaPdfUseCase:
    """
    Use case for generating proforma PDFs.

    Flow:
    1. Load invoice and audit data
    2. Render PDF via ProformaPdfService
    3. Return PDF bytes and metadata
    """

    def __init__(
        self,
        pdf_service: ProformaPdfService | None = None,
    ):
        self._pdf_service = pdf_service

    def _get_pdf_service(self) -> ProformaPdfService:
        if self._pdf_service is None:
            from src.application.services import get_proforma_pdf_service

            self._pdf_service = get_proforma_pdf_service()
        return self._pdf_service

    async def execute(self, invoice_id: int) -> ProformaPdfResult:
        """
        Generate proforma PDF for the given invoice.

        Args:
            invoice_id: The invoice ID.

        Returns:
            ProformaPdfResult with PDF bytes and metadata.
        """
        logger.info("generate_proforma_pdf_started", invoice_id=invoice_id)
        service = self._get_pdf_service()
        result = await service.generate_proforma_pdf(invoice_id)
        logger.info(
            "generate_proforma_pdf_complete",
            invoice_id=invoice_id,
            file_size=result.file_size,
        )
        return result

    @staticmethod
    def to_response(result: ProformaPdfResult) -> ProformaPdfResponse:
        """Convert result to API response."""
        return ProformaPdfResponse(
            invoice_id=str(result.invoice_id),
            file_path=result.file_path,
            file_size=result.file_size,
        )
