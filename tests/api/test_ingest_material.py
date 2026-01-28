"""API smoke tests for material ingestion endpoint."""

from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_ingest_material_use_case
from src.api.main import app
from src.application.dto.responses import (
    IngestMaterialResponse,
    MaterialResponse,
)
from src.core.entities.material import Material, OriginConfidence
from src.core.interfaces.product_fetcher import ProductPageData
from src.core.services.material_ingestion import IngestionResult


def _make_mock_use_case(created: bool = True):
    """Create a mock IngestMaterialUseCase."""
    material = Material(
        id="mat-ingest-001",
        name="BOSCH Impact Drill 500W",
        normalized_name="bosch impact drill 500w",
        brand="BOSCH",
        source_url="https://www.amazon.ae/dp/B001",
        origin_country="Germany",
        origin_confidence=OriginConfidence.CONFIRMED,
        evidence_text="Country of Origin: Germany",
        category="Power Tools",
        unit="PCS",
    )
    page_data = ProductPageData(
        title="BOSCH Impact Drill 500W",
        brand="BOSCH",
        description="Professional impact drill",
        origin_country="Germany",
        origin_confidence=OriginConfidence.CONFIRMED,
        evidence_text="Country of Origin: Germany",
        source_url="https://www.amazon.ae/dp/B001",
        category="Power Tools",
        suggested_synonyms=["Impact Drill 500W"],
    )
    result = IngestionResult(
        material=material,
        page_data=page_data,
        created=created,
        synonyms_added=["Impact Drill 500W"] if created else [],
    )
    response = IngestMaterialResponse(
        material=MaterialResponse(
            id=material.id or "",
            name=material.name,
            normalized_name=material.normalized_name,
            hs_code=material.hs_code,
            category=material.category,
            unit=material.unit,
            description=material.description,
            brand=material.brand,
            source_url=material.source_url,
            origin_country=material.origin_country,
            origin_confidence=material.origin_confidence.value,
            synonyms=[],
            created_at=material.created_at,
            updated_at=material.updated_at,
        ),
        created=created,
        synonyms_added=["Impact Drill 500W"] if created else [],
        source_url="https://www.amazon.ae/dp/B001",
        brand="BOSCH",
        origin_country="Germany",
        origin_confidence="confirmed",
        evidence_text="Country of Origin: Germany",
    )

    uc = Mock()
    uc.execute = AsyncMock(return_value=result)
    uc.to_response = Mock(return_value=response)
    return uc


@pytest.fixture
async def ingest_client():
    """Async client with ingest use case overridden."""
    mock_uc = _make_mock_use_case()
    app.dependency_overrides[get_ingest_material_use_case] = lambda: mock_uc
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_ingest_material_use_case, None)


class TestIngestMaterialAPI:
    """Tests for POST /api/catalog/ingest endpoint."""

    async def test_ingest_endpoint_exists(self, ingest_client: AsyncClient):
        """POST /api/catalog/ingest returns non-404."""
        response = await ingest_client.post(
            "/api/catalog/ingest",
            json={"url": "https://www.amazon.ae/dp/B001"},
        )
        assert response.status_code != 404

    async def test_ingest_returns_201(self, ingest_client: AsyncClient):
        """POST /api/catalog/ingest returns 201 for new material."""
        response = await ingest_client.post(
            "/api/catalog/ingest",
            json={"url": "https://www.amazon.ae/dp/B001"},
        )
        assert response.status_code == 201

    async def test_ingest_response_shape(self, ingest_client: AsyncClient):
        """Response contains expected ingestion fields."""
        response = await ingest_client.post(
            "/api/catalog/ingest",
            json={"url": "https://www.amazon.ae/dp/B001"},
        )
        data = response.json()
        assert "material" in data
        assert "created" in data
        assert "source_url" in data
        assert "brand" in data
        assert "origin_country" in data
        assert "origin_confidence" in data
        assert "synonyms_added" in data

    async def test_ingest_material_fields(self, ingest_client: AsyncClient):
        """Material in response has ingestion fields."""
        response = await ingest_client.post(
            "/api/catalog/ingest",
            json={"url": "https://www.amazon.ae/dp/B001"},
        )
        mat = response.json()["material"]
        assert mat["id"] == "mat-ingest-001"
        assert mat["name"] == "BOSCH Impact Drill 500W"
        assert mat["brand"] == "BOSCH"
        assert mat["origin_country"] == "Germany"
        assert mat["origin_confidence"] == "confirmed"
        assert mat["source_url"] == "https://www.amazon.ae/dp/B001"

    async def test_ingest_with_optional_params(self, ingest_client: AsyncClient):
        """Request accepts optional category and unit."""
        response = await ingest_client.post(
            "/api/catalog/ingest",
            json={
                "url": "https://www.amazon.ae/dp/B001",
                "category": "Power Tools",
                "unit": "PCS",
            },
        )
        assert response.status_code == 201

    async def test_ingest_missing_url_returns_422(self, ingest_client: AsyncClient):
        """Missing url field returns 422 validation error."""
        response = await ingest_client.post(
            "/api/catalog/ingest",
            json={},
        )
        assert response.status_code == 422
