"""API smoke tests for catalog endpoints."""

from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_add_to_catalog_use_case, get_mat_store
from src.api.main import app
from src.application.use_cases.add_to_catalog import AddToCatalogResult
from src.core.entities.material import Material


@pytest.fixture
def mock_material_store():
    """Create mock material store."""
    store = AsyncMock()
    sample = Material(
        id="mat-abc",
        name="PVC Cable 10mm",
        normalized_name="pvc cable 10mm",
        hs_code="8544.42",
        unit="M",
    )
    store.list_materials.return_value = [sample]
    store.search_by_name.return_value = [sample]
    store.get_material.return_value = sample
    return store


@pytest.fixture
def mock_use_case():
    """Create mock add-to-catalog use case."""
    from src.application.dto.responses import (
        AddToCatalogResponse,
        MaterialResponse,
    )

    mat = Material(
        id="mat-abc",
        name="PVC Cable 10mm",
        normalized_name="pvc cable 10mm",
        hs_code="8544.42",
        unit="M",
    )
    result = AddToCatalogResult(
        materials_created=1,
        materials_updated=0,
        materials=[mat],
    )
    response = AddToCatalogResponse(
        materials_created=1,
        materials_updated=0,
        materials=[
            MaterialResponse(
                id=mat.id or "",
                name=mat.name,
                normalized_name=mat.normalized_name,
                hs_code=mat.hs_code,
                category=mat.category,
                unit=mat.unit,
                description=mat.description,
                synonyms=[],
                created_at=mat.created_at,
                updated_at=mat.updated_at,
            )
        ],
    )

    uc = Mock()
    uc.execute = AsyncMock(return_value=result)
    uc.to_response = Mock(return_value=response)
    return uc


@pytest.fixture
async def catalog_client(mock_material_store, mock_use_case):
    """Async client with catalog dependencies overridden."""
    app.dependency_overrides[get_mat_store] = lambda: mock_material_store
    app.dependency_overrides[get_add_to_catalog_use_case] = lambda: mock_use_case
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_mat_store, None)
    app.dependency_overrides.pop(get_add_to_catalog_use_case, None)


class TestCatalogAPI:
    """Smoke tests for catalog API."""

    async def test_post_catalog_endpoint_exists(self, catalog_client: AsyncClient):
        """Test that POST /api/catalog/ endpoint exists."""
        response = await catalog_client.post(
            "/api/catalog/",
            json={"invoice_id": 1, "item_ids": [10, 11]},
        )
        assert response.status_code != 404

    async def test_post_catalog_returns_created(self, catalog_client: AsyncClient):
        """Test that POST /api/catalog/ returns 201 with materials."""
        response = await catalog_client.post(
            "/api/catalog/",
            json={"invoice_id": 1},
        )
        assert response.status_code == 201
        data = response.json()
        assert "materials_created" in data
        assert "materials" in data
        assert data["materials_created"] == 1

    async def test_list_catalog_endpoint_exists(self, catalog_client: AsyncClient):
        """Test that GET /api/catalog/ endpoint exists."""
        response = await catalog_client.get("/api/catalog/")
        assert response.status_code != 404

    async def test_list_catalog_returns_materials(self, catalog_client: AsyncClient):
        """Test that GET /api/catalog/ returns material list."""
        response = await catalog_client.get("/api/catalog/")
        assert response.status_code == 200
        data = response.json()
        assert "materials" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_list_catalog_with_search(self, catalog_client: AsyncClient):
        """Test that GET /api/catalog/?q=... accepts search."""
        response = await catalog_client.get(
            "/api/catalog/", params={"q": "cable"}
        )
        assert response.status_code == 200

    async def test_get_material_endpoint_exists(self, catalog_client: AsyncClient):
        """Test that GET /api/catalog/{id} endpoint exists."""
        response = await catalog_client.get("/api/catalog/mat-abc")
        assert response.status_code != 404

    async def test_get_material_returns_detail(self, catalog_client: AsyncClient):
        """Test that GET /api/catalog/{id} returns material with synonyms."""
        response = await catalog_client.get("/api/catalog/mat-abc")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "mat-abc"
        assert data["name"] == "PVC Cable 10mm"
        assert "synonyms" in data


class TestCatalogExport:
    """Tests for GET /api/catalog/export."""

    async def test_export_json_default(self, catalog_client: AsyncClient):
        """Test that export defaults to JSON format."""
        response = await catalog_client.get("/api/catalog/export")
        assert response.status_code == 200
        data = response.json()
        assert "materials" in data
        assert "total" in data
        assert data["total"] >= 1
        assert data["materials"][0]["name"] == "PVC Cable 10mm"

    async def test_export_json_explicit(self, catalog_client: AsyncClient):
        """Test explicit JSON export format."""
        response = await catalog_client.get("/api/catalog/export?format=json")
        assert response.status_code == 200
        data = response.json()
        assert "materials" in data

    async def test_export_csv(self, catalog_client: AsyncClient):
        """Test CSV export format returns CSV content."""
        response = await catalog_client.get("/api/catalog/export?format=csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert "catalog_export.csv" in response.headers.get("content-disposition", "")
        # Verify CSV content has header and data
        lines = response.text.strip().split("\n")
        assert len(lines) >= 2  # header + at least one data row
        assert "name" in lines[0]
        assert "PVC Cable 10mm" in lines[1]

    async def test_export_invalid_format(self, catalog_client: AsyncClient):
        """Test that invalid format returns 422."""
        response = await catalog_client.get("/api/catalog/export?format=xml")
        assert response.status_code == 422
