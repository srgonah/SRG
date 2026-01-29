"""API tests for catalog match endpoint."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_catalog_matcher, get_mat_store
from src.api.main import app
from src.core.entities.material import Material
from src.core.services.catalog_matcher import CatalogMatcher, MatchCandidate


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
    store.get_material.return_value = sample
    store.list_materials.return_value = [sample]
    store.find_by_normalized_name.return_value = None
    store.find_by_synonym.return_value = None
    return store


@pytest.fixture
def mock_matcher():
    """Create mock catalog matcher."""
    matcher = AsyncMock(spec=CatalogMatcher)
    matcher.find_matches = AsyncMock(
        return_value=[
            MatchCandidate(
                material_id="mat-abc",
                material_name="PVC Cable 10mm",
                score=0.85,
                match_type="fuzzy",
            ),
            MatchCandidate(
                material_id="mat-def",
                material_name="PVC Cable 12mm",
                score=0.72,
                match_type="fuzzy",
            ),
        ]
    )
    return matcher


@pytest.fixture
async def match_client(mock_material_store, mock_matcher):
    """Async client with catalog match dependencies overridden."""
    app.dependency_overrides[get_mat_store] = lambda: mock_material_store
    app.dependency_overrides[get_catalog_matcher] = lambda: mock_matcher
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_mat_store, None)
    app.dependency_overrides.pop(get_catalog_matcher, None)


@pytest.mark.asyncio
class TestCatalogMatchesAPI:
    """Tests for GET /api/catalog/{material_id}/matches."""

    async def test_matches_endpoint_exists(self, match_client: AsyncClient):
        """Test that the matches endpoint exists and is reachable."""
        response = await match_client.get(
            "/api/catalog/mat-abc/matches",
            params={"query": "pvc cable"},
        )
        assert response.status_code != 404

    async def test_matches_returns_candidates(self, match_client: AsyncClient):
        """Test that matches returns a list of scored candidates."""
        response = await match_client.get(
            "/api/catalog/mat-abc/matches",
            params={"query": "pvc cable"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["material_id"] == "mat-abc"
        assert data[0]["score"] == 0.85
        assert data[0]["match_type"] == "fuzzy"

    async def test_matches_requires_query_param(self, match_client: AsyncClient):
        """Test that query parameter is required."""
        response = await match_client.get("/api/catalog/mat-abc/matches")
        assert response.status_code == 422  # Validation error

    async def test_matches_material_not_found(
        self, mock_material_store, mock_matcher
    ):
        """Test 404 when material does not exist."""
        mock_material_store.get_material.return_value = None
        app.dependency_overrides[get_mat_store] = lambda: mock_material_store
        app.dependency_overrides[get_catalog_matcher] = lambda: mock_matcher
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/catalog/nonexistent/matches",
                params={"query": "test"},
            )
        app.dependency_overrides.pop(get_mat_store, None)
        app.dependency_overrides.pop(get_catalog_matcher, None)
        assert response.status_code == 404

    async def test_matches_respects_top_k(
        self, match_client: AsyncClient, mock_matcher
    ):
        """Test that top_k parameter is passed to the matcher."""
        await match_client.get(
            "/api/catalog/mat-abc/matches",
            params={"query": "pvc cable", "top_k": 3},
        )
        mock_matcher.find_matches.assert_awaited_once_with("pvc cable", top_k=3)

    async def test_matches_response_structure(self, match_client: AsyncClient):
        """Test that each candidate has the expected fields."""
        response = await match_client.get(
            "/api/catalog/mat-abc/matches",
            params={"query": "cable"},
        )
        assert response.status_code == 200
        data = response.json()
        for candidate in data:
            assert "material_id" in candidate
            assert "material_name" in candidate
            assert "score" in candidate
            assert "match_type" in candidate
