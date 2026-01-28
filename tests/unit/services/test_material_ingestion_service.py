"""Unit tests for MaterialIngestionService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.entities.material import Material, OriginConfidence
from src.core.exceptions import CatalogError
from src.core.interfaces.product_fetcher import IProductPageFetcher, ProductPageData
from src.core.services.material_ingestion import IngestionResult, MaterialIngestionService


def _make_page_data(**overrides) -> ProductPageData:
    """Create a ProductPageData with defaults."""
    defaults = {
        "title": "BOSCH Impact Drill 500W",
        "brand": "BOSCH",
        "description": "Professional impact drill",
        "origin_country": "Germany",
        "origin_confidence": OriginConfidence.CONFIRMED,
        "evidence_text": "Country of Origin: Germany",
        "source_url": "https://www.amazon.ae/dp/B001",
        "category": "Power Tools",
        "suggested_synonyms": ["Impact Drill 500W", "BOSCH"],
    }
    defaults.update(overrides)
    return ProductPageData(**defaults)


def _make_fetcher(supports: bool = True, page_data: ProductPageData | None = None):
    """Create a mock IProductPageFetcher."""
    fetcher = MagicMock(spec=IProductPageFetcher)
    fetcher.supports_url.return_value = supports
    fetcher.fetch = AsyncMock(return_value=page_data or _make_page_data())
    return fetcher


def _make_store():
    """Create a mock IMaterialStore."""
    store = AsyncMock()
    store.find_by_normalized_name = AsyncMock(return_value=None)
    store.create_material = AsyncMock(
        side_effect=lambda m: Material(
            id="mat-new-001",
            name=m.name,
            normalized_name=m.normalized_name,
            category=m.category,
            unit=m.unit,
            description=m.description,
            brand=m.brand,
            source_url=m.source_url,
            origin_country=m.origin_country,
            origin_confidence=m.origin_confidence,
            evidence_text=m.evidence_text,
        )
    )
    store.update_material = AsyncMock(side_effect=lambda m: m)
    store.add_synonym = AsyncMock()
    return store


class TestIngestionServiceNewMaterial:
    """Tests for creating new materials via ingestion."""

    async def test_ingest_creates_material_when_not_found(self):
        """Service creates a new material when no match exists."""
        fetcher = _make_fetcher()
        store = _make_store()
        service = MaterialIngestionService(fetchers=[fetcher], material_store=store)

        result = await service.ingest_from_url("https://www.amazon.ae/dp/B001")

        assert isinstance(result, IngestionResult)
        assert result.created is True
        assert result.material.id == "mat-new-001"
        assert result.material.name == "BOSCH Impact Drill 500W"
        assert result.material.brand == "BOSCH"
        assert result.material.origin_country == "Germany"
        store.create_material.assert_awaited_once()

    async def test_ingest_passes_category_and_unit(self):
        """Category and unit overrides are passed to created material."""
        fetcher = _make_fetcher()
        store = _make_store()
        service = MaterialIngestionService(fetchers=[fetcher], material_store=store)

        result = await service.ingest_from_url(
            "https://www.amazon.ae/dp/B001",
            category="Hardware",
            unit="PCS",
        )

        assert result.material.category == "Hardware"
        assert result.material.unit == "PCS"

    async def test_ingest_adds_synonyms_for_new_material(self):
        """Synonyms are added for newly created materials."""
        fetcher = _make_fetcher()
        store = _make_store()
        service = MaterialIngestionService(fetchers=[fetcher], material_store=store)

        result = await service.ingest_from_url("https://www.amazon.ae/dp/B001")

        assert len(result.synonyms_added) == 2
        assert store.add_synonym.await_count == 2


class TestIngestionServiceExistingMaterial:
    """Tests for updating existing materials via ingestion."""

    async def test_ingest_updates_existing_material(self):
        """Service updates an existing material when match found."""
        existing = Material(
            id="mat-existing-001",
            name="BOSCH Impact Drill 500W",
            normalized_name="bosch impact drill 500w",
            brand="BOSCH",
        )

        fetcher = _make_fetcher()
        store = _make_store()
        store.find_by_normalized_name.return_value = existing
        service = MaterialIngestionService(fetchers=[fetcher], material_store=store)

        result = await service.ingest_from_url("https://www.amazon.ae/dp/B001")

        assert result.created is False
        assert result.material.id == "mat-existing-001"
        store.update_material.assert_awaited_once()
        store.create_material.assert_not_awaited()

    async def test_ingest_preserves_existing_brand_if_no_new(self):
        """Existing brand is preserved when new data has no brand."""
        existing = Material(
            id="mat-existing-001",
            name="Some Drill",
            normalized_name="some drill",
            brand="ExistingBrand",
        )

        page_data = _make_page_data(brand=None)
        fetcher = _make_fetcher(page_data=page_data)
        store = _make_store()
        store.find_by_normalized_name.return_value = existing
        service = MaterialIngestionService(fetchers=[fetcher], material_store=store)

        result = await service.ingest_from_url("https://www.amazon.ae/dp/B001")

        assert result.material.brand == "ExistingBrand"

    async def test_ingest_skips_existing_synonyms(self):
        """Already-existing synonyms are not re-added."""
        existing = Material(
            id="mat-existing-001",
            name="BOSCH Impact Drill 500W",
            normalized_name="bosch impact drill 500w",
            synonyms=["Impact Drill 500W"],
        )

        fetcher = _make_fetcher()
        store = _make_store()
        store.find_by_normalized_name.return_value = existing
        service = MaterialIngestionService(fetchers=[fetcher], material_store=store)

        result = await service.ingest_from_url("https://www.amazon.ae/dp/B001")

        # "Impact Drill 500W" already exists, only "BOSCH" should be added
        assert "BOSCH" in result.synonyms_added
        assert "Impact Drill 500W" not in result.synonyms_added


class TestIngestionServiceErrors:
    """Tests for error handling in ingestion service."""

    async def test_unsupported_url_raises(self):
        """CatalogError raised when no fetcher supports the URL."""
        fetcher = _make_fetcher(supports=False)
        store = _make_store()
        service = MaterialIngestionService(fetchers=[fetcher], material_store=store)

        with pytest.raises(CatalogError, match="No fetcher supports"):
            await service.ingest_from_url("https://unknown-site.com/product/123")

    async def test_no_fetchers_raises(self):
        """CatalogError raised when fetcher list is empty."""
        store = _make_store()
        service = MaterialIngestionService(fetchers=[], material_store=store)

        with pytest.raises(CatalogError, match="No fetcher supports"):
            await service.ingest_from_url("https://www.amazon.ae/dp/B001")


class TestIngestionServiceHelpers:
    """Tests for helper methods."""

    def test_normalize_name(self):
        """Name normalization strips, lowercases, collapses whitespace."""
        store = _make_store()
        service = MaterialIngestionService(fetchers=[], material_store=store)

        assert service._normalize_name("  BOSCH  Drill  500W  ") == "bosch drill 500w"
        assert service._normalize_name("Widget") == "widget"
        assert service._normalize_name("A  B   C") == "a b c"

    def test_find_fetcher_returns_supporting(self):
        """_find_fetcher returns the first supporting fetcher."""
        f1 = _make_fetcher(supports=False)
        f2 = _make_fetcher(supports=True)
        store = _make_store()
        service = MaterialIngestionService(fetchers=[f1, f2], material_store=store)

        result = service._find_fetcher("https://www.amazon.ae/dp/B001")
        assert result is f2

    def test_find_fetcher_returns_none_when_unsupported(self):
        """_find_fetcher returns None when no fetcher supports."""
        f1 = _make_fetcher(supports=False)
        store = _make_store()
        service = MaterialIngestionService(fetchers=[f1], material_store=store)

        assert service._find_fetcher("https://example.com") is None
