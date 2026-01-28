"""Unit tests for IngestMaterialUseCase."""

from unittest.mock import AsyncMock, MagicMock

from src.application.dto.requests import IngestMaterialRequest
from src.application.dto.responses import IngestMaterialResponse
from src.application.use_cases.ingest_material import IngestMaterialUseCase
from src.core.entities.material import Material, OriginConfidence
from src.core.interfaces.product_fetcher import ProductPageData
from src.core.services.material_ingestion import IngestionResult


def _make_result(created: bool = True) -> IngestionResult:
    """Create a sample IngestionResult."""
    material = Material(
        id="mat-001",
        name="BOSCH Drill 500W",
        normalized_name="bosch drill 500w",
        brand="BOSCH",
        source_url="https://www.amazon.ae/dp/B001",
        origin_country="Germany",
        origin_confidence=OriginConfidence.CONFIRMED,
        evidence_text="Country of Origin: Germany",
        category="Power Tools",
    )
    page_data = ProductPageData(
        title="BOSCH Drill 500W",
        brand="BOSCH",
        description="Professional drill",
        origin_country="Germany",
        origin_confidence=OriginConfidence.CONFIRMED,
        evidence_text="Country of Origin: Germany",
        source_url="https://www.amazon.ae/dp/B001",
        category="Power Tools",
        suggested_synonyms=["Drill 500W"],
    )
    return IngestionResult(
        material=material,
        page_data=page_data,
        created=created,
        synonyms_added=["Drill 500W"] if created else [],
    )


class TestIngestMaterialUseCase:
    """Tests for IngestMaterialUseCase."""

    async def test_execute_calls_service(self):
        """execute() delegates to the ingestion service."""
        mock_service = MagicMock()
        mock_service.ingest_from_url = AsyncMock(return_value=_make_result())
        uc = IngestMaterialUseCase(ingestion_service=mock_service)

        request = IngestMaterialRequest(
            url="https://www.amazon.ae/dp/B001",
            category="Tools",
            unit="PCS",
        )
        result = await uc.execute(request)

        assert isinstance(result, IngestionResult)
        assert result.created is True
        mock_service.ingest_from_url.assert_awaited_once_with(
            url="https://www.amazon.ae/dp/B001",
            category="Tools",
            unit="PCS",
        )

    def test_to_response_new_material(self):
        """to_response() returns correct response for new material."""
        uc = IngestMaterialUseCase(ingestion_service=MagicMock())
        result = _make_result(created=True)

        response = uc.to_response(result)

        assert isinstance(response, IngestMaterialResponse)
        assert response.created is True
        assert response.material.id == "mat-001"
        assert response.material.name == "BOSCH Drill 500W"
        assert response.material.brand == "BOSCH"
        assert response.material.origin_country == "Germany"
        assert response.material.origin_confidence == "confirmed"
        assert response.source_url == "https://www.amazon.ae/dp/B001"
        assert response.brand == "BOSCH"
        assert response.origin_country == "Germany"
        assert response.origin_confidence == "confirmed"
        assert response.evidence_text == "Country of Origin: Germany"
        assert "Drill 500W" in response.synonyms_added

    def test_to_response_updated_material(self):
        """to_response() marks created=False for updates."""
        uc = IngestMaterialUseCase(ingestion_service=MagicMock())
        result = _make_result(created=False)

        response = uc.to_response(result)

        assert response.created is False
        assert response.synonyms_added == []
