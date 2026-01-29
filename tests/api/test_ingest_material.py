"""API smoke tests for material ingestion endpoint.

Covers:
- Single ingest endpoint (POST /api/catalog/ingest)
- Batch ingest endpoint (POST /api/catalog/ingest/batch)
- Preview endpoint (POST /api/catalog/ingest/preview)
"""

from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_ingest_material_use_case
from src.api.main import app
from src.application.dto.responses import (
    IngestMaterialResponse,
    MaterialResponse,
)
from src.core.entities.material import Material, OriginConfidence
from src.core.exceptions import CatalogError
from src.core.interfaces.product_fetcher import ProductPageData
from src.core.services.material_ingestion import IngestionResult


def _make_page_data(
    url: str = "https://www.amazon.ae/dp/B001",
) -> ProductPageData:
    """Create sample ProductPageData."""
    return ProductPageData(
        title="BOSCH Impact Drill 500W",
        brand="BOSCH",
        description="Professional impact drill",
        origin_country="Germany",
        origin_confidence=OriginConfidence.CONFIRMED,
        evidence_text="Country of Origin: Germany",
        source_url=url,
        category="Power Tools",
        suggested_synonyms=["Impact Drill 500W"],
        asin="B09V3KXJPB",
        weight="2.5 kg",
        dimensions="30 x 20 x 10 cm",
        price="AED149.99",
        rating=4.5,
        num_ratings=1234,
    )


def _make_material(
    url: str = "https://www.amazon.ae/dp/B001",
) -> Material:
    """Create sample Material."""
    return Material(
        id="mat-ingest-001",
        name="BOSCH Impact Drill 500W",
        normalized_name="bosch impact drill 500w",
        brand="BOSCH",
        source_url=url,
        origin_country="Germany",
        origin_confidence=OriginConfidence.CONFIRMED,
        evidence_text="Country of Origin: Germany",
        category="Power Tools",
        unit="PCS",
    )


def _make_mock_use_case(created: bool = True):
    """Create a mock IngestMaterialUseCase."""
    material = _make_material()
    page_data = _make_page_data()
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


def _make_mock_use_case_for_batch(*, fail_urls: set[str] | None = None):
    """Create a mock use case that can selectively fail for batch tests."""
    fail_urls = fail_urls or set()

    async def mock_execute(request):
        if request.url in fail_urls:
            raise CatalogError(
                f"No fetcher supports the URL: {request.url}",
                code="UNSUPPORTED_URL",
            )
        material = _make_material(request.url)
        page_data = _make_page_data(request.url)
        return IngestionResult(
            material=material,
            page_data=page_data,
            created=True,
            synonyms_added=[],
        )

    def mock_to_response(result):
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
                synonyms=[],
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

    uc = Mock()
    uc.execute = AsyncMock(side_effect=mock_execute)
    uc.to_response = Mock(side_effect=mock_to_response)
    return uc


def _make_mock_use_case_for_preview():
    """Create a mock use case with fetcher support for preview tests."""
    page_data = _make_page_data()

    mock_fetcher = Mock()
    mock_fetcher.supports_url.return_value = True
    mock_fetcher.fetch = AsyncMock(return_value=page_data)

    mock_service = Mock()
    mock_service._find_fetcher = Mock(return_value=mock_fetcher)

    uc = Mock()
    uc._get_service = Mock(return_value=mock_service)
    uc.execute = AsyncMock()  # Not used for preview
    uc.to_response = Mock()
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


@pytest.fixture
async def batch_client():
    """Async client for batch ingest tests."""
    mock_uc = _make_mock_use_case_for_batch(
        fail_urls={"https://www.aliexpress.com/item/123"}
    )
    app.dependency_overrides[get_ingest_material_use_case] = lambda: mock_uc
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_ingest_material_use_case, None)


@pytest.fixture
async def preview_client():
    """Async client for preview endpoint tests."""
    mock_uc = _make_mock_use_case_for_preview()
    app.dependency_overrides[get_ingest_material_use_case] = lambda: mock_uc
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_ingest_material_use_case, None)


# ==========================================================================
# Single ingest endpoint tests
# ==========================================================================


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


# ==========================================================================
# Batch ingest endpoint tests (Task 3.4)
# ==========================================================================


class TestBatchIngestAPI:
    """Tests for POST /api/catalog/ingest/batch endpoint."""

    async def test_batch_endpoint_exists(self, batch_client: AsyncClient):
        """POST /api/catalog/ingest/batch returns non-404."""
        response = await batch_client.post(
            "/api/catalog/ingest/batch",
            json={"urls": ["https://www.amazon.ae/dp/B001"]},
        )
        assert response.status_code != 404

    async def test_batch_returns_200(self, batch_client: AsyncClient):
        """Successful batch returns 200."""
        response = await batch_client.post(
            "/api/catalog/ingest/batch",
            json={"urls": ["https://www.amazon.ae/dp/B001"]},
        )
        assert response.status_code == 200

    async def test_batch_response_shape(self, batch_client: AsyncClient):
        """Response has results, total, succeeded, failed."""
        response = await batch_client.post(
            "/api/catalog/ingest/batch",
            json={"urls": ["https://www.amazon.ae/dp/B001"]},
        )
        data = response.json()
        assert "results" in data
        assert "total" in data
        assert "succeeded" in data
        assert "failed" in data

    async def test_batch_all_succeed(self, batch_client: AsyncClient):
        """All valid URLs succeed."""
        response = await batch_client.post(
            "/api/catalog/ingest/batch",
            json={
                "urls": [
                    "https://www.amazon.ae/dp/B001",
                    "https://www.amazon.ae/dp/B002",
                ]
            },
        )
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        assert all(r["status"] == "success" for r in data["results"])

    async def test_batch_partial_failure(self, batch_client: AsyncClient):
        """Invalid URL fails while valid URL succeeds."""
        response = await batch_client.post(
            "/api/catalog/ingest/batch",
            json={
                "urls": [
                    "https://www.amazon.ae/dp/B001",
                    "https://www.aliexpress.com/item/123",
                ]
            },
        )
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1

        success = [r for r in data["results"] if r["status"] == "success"]
        errors = [r for r in data["results"] if r["status"] == "error"]
        assert len(success) == 1
        assert success[0]["material_id"] is not None
        assert len(errors) == 1
        assert errors[0]["error"] is not None

    async def test_batch_per_url_result_has_url(self, batch_client: AsyncClient):
        """Each result item includes the original URL."""
        response = await batch_client.post(
            "/api/catalog/ingest/batch",
            json={"urls": ["https://www.amazon.ae/dp/B001"]},
        )
        data = response.json()
        assert data["results"][0]["url"] == "https://www.amazon.ae/dp/B001"

    async def test_batch_empty_urls_returns_422(self, batch_client: AsyncClient):
        """Empty urls list returns 422 validation error."""
        response = await batch_client.post(
            "/api/catalog/ingest/batch",
            json={"urls": []},
        )
        assert response.status_code == 422

    async def test_batch_too_many_urls_returns_422(self, batch_client: AsyncClient):
        """More than 20 URLs returns 422 validation error."""
        urls = [f"https://www.amazon.ae/dp/B{i:09d}" for i in range(21)]
        response = await batch_client.post(
            "/api/catalog/ingest/batch",
            json={"urls": urls},
        )
        assert response.status_code == 422


# ==========================================================================
# Preview endpoint tests (Task 3.5)
# ==========================================================================


class TestPreviewIngestAPI:
    """Tests for POST /api/catalog/ingest/preview endpoint."""

    async def test_preview_endpoint_exists(self, preview_client: AsyncClient):
        """POST /api/catalog/ingest/preview returns non-404."""
        response = await preview_client.post(
            "/api/catalog/ingest/preview",
            json={"url": "https://www.amazon.ae/dp/B001"},
        )
        assert response.status_code != 404

    async def test_preview_returns_200(self, preview_client: AsyncClient):
        """Preview returns 200 (not 201 since nothing is saved)."""
        response = await preview_client.post(
            "/api/catalog/ingest/preview",
            json={"url": "https://www.amazon.ae/dp/B001"},
        )
        assert response.status_code == 200

    async def test_preview_response_shape(self, preview_client: AsyncClient):
        """Response has product data fields."""
        response = await preview_client.post(
            "/api/catalog/ingest/preview",
            json={"url": "https://www.amazon.ae/dp/B001"},
        )
        data = response.json()
        assert "title" in data
        assert "brand" in data
        assert "description" in data
        assert "category" in data
        assert "origin_country" in data
        assert "origin_confidence" in data
        assert "source_url" in data
        assert "suggested_synonyms" in data
        assert "raw_attributes" in data

    async def test_preview_includes_extended_fields(self, preview_client: AsyncClient):
        """Response includes ASIN, weight, dimensions, price, rating."""
        response = await preview_client.post(
            "/api/catalog/ingest/preview",
            json={"url": "https://www.amazon.ae/dp/B001"},
        )
        data = response.json()
        assert "asin" in data
        assert "weight" in data
        assert "dimensions" in data
        assert "price" in data
        assert "rating" in data
        assert "num_ratings" in data

    async def test_preview_returns_data_values(self, preview_client: AsyncClient):
        """Preview returns the correct parsed values."""
        response = await preview_client.post(
            "/api/catalog/ingest/preview",
            json={"url": "https://www.amazon.ae/dp/B001"},
        )
        data = response.json()
        assert data["title"] == "BOSCH Impact Drill 500W"
        assert data["brand"] == "BOSCH"
        assert data["origin_country"] == "Germany"
        assert data["asin"] == "B09V3KXJPB"
        assert data["weight"] == "2.5 kg"
        assert data["price"] == "AED149.99"
        assert data["rating"] == 4.5
        assert data["num_ratings"] == 1234

    async def test_preview_does_not_save_material(self, preview_client: AsyncClient):
        """Preview does not call execute (which would save to DB)."""
        response = await preview_client.post(
            "/api/catalog/ingest/preview",
            json={"url": "https://www.amazon.ae/dp/B001"},
        )
        assert response.status_code == 200
        # The mock's execute should NOT have been called
        mock_uc = app.dependency_overrides[get_ingest_material_use_case]()
        mock_uc.execute.assert_not_called()

    async def test_preview_missing_url_returns_422(self, preview_client: AsyncClient):
        """Missing url field returns 422 validation error."""
        response = await preview_client.post(
            "/api/catalog/ingest/preview",
            json={},
        )
        assert response.status_code == 422
