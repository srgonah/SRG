"""
Use case: Ingest material from external product URL.

Fetches product data from an e-commerce URL, creates or updates
a material in the catalog, and returns the result.
"""

from src.application.dto.requests import IngestMaterialRequest
from src.application.dto.responses import (
    IngestMaterialResponse,
    MaterialResponse,
    MaterialSynonymResponse,
)
from src.config import get_logger
from src.core.services.material_ingestion import IngestionResult, MaterialIngestionService

logger = get_logger(__name__)


class IngestMaterialUseCase:
    """Orchestrates material ingestion from external URLs."""

    def __init__(self, ingestion_service: MaterialIngestionService | None = None):
        self._service = ingestion_service

    def _get_service(self) -> MaterialIngestionService:
        """Lazy-load the ingestion service."""
        if self._service is not None:
            return self._service

        from src.application.services import get_material_ingestion_service

        self._service = get_material_ingestion_service()
        return self._service

    async def execute(self, request: IngestMaterialRequest) -> IngestionResult:
        """Execute the ingestion use case."""
        service = self._get_service()
        result = await service.ingest_from_url(
            url=request.url,
            category=request.category,
            unit=request.unit,
        )
        logger.info(
            "material_ingested",
            material_id=result.material.id,
            created=result.created,
            url=request.url,
        )
        return result

    def to_response(self, result: IngestionResult) -> IngestMaterialResponse:
        """Convert ingestion result to API response."""
        m = result.material
        return IngestMaterialResponse(
            material=MaterialResponse(
                id=m.id or "",
                name=m.name,
                normalized_name=m.normalized_name,
                hs_code=m.hs_code,
                category=m.category,
                unit=m.unit,
                description=m.description,
                brand=m.brand,
                source_url=m.source_url,
                origin_country=m.origin_country,
                origin_confidence=m.origin_confidence.value,
                synonyms=[
                    MaterialSynonymResponse(id="", synonym=s, language="en")
                    for s in m.synonyms
                ],
                created_at=m.created_at,
                updated_at=m.updated_at,
            ),
            created=result.created,
            synonyms_added=result.synonyms_added,
            source_url=result.page_data.source_url,
            brand=result.page_data.brand,
            origin_country=result.page_data.origin_country,
            origin_confidence=result.page_data.origin_confidence.value,
            evidence_text=result.page_data.evidence_text,
        )
