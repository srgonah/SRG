"""
Material ingestion service.

Orchestrates fetching product data from external URLs
and creating/updating materials in the catalog.
"""

import re

from src.config import get_logger
from src.core.entities.material import Material
from src.core.interfaces.material_store import IMaterialStore
from src.core.interfaces.product_fetcher import IProductPageFetcher, ProductPageData

logger = get_logger(__name__)


class IngestionResult:
    """Result of a material ingestion operation."""

    def __init__(
        self,
        material: Material,
        page_data: ProductPageData,
        created: bool,
        synonyms_added: list[str],
    ):
        self.material = material
        self.page_data = page_data
        self.created = created
        self.synonyms_added = synonyms_added


class MaterialIngestionService:
    """
    Service for ingesting material data from external product pages.

    Fetches product data from a URL, normalizes it, and creates or
    updates a material in the catalog. Pure service — no infrastructure
    imports; all dependencies injected via constructor.
    """

    def __init__(
        self,
        fetchers: list[IProductPageFetcher],
        material_store: IMaterialStore,
    ):
        self._fetchers = fetchers
        self._material_store = material_store

    async def ingest_from_url(
        self,
        url: str,
        *,
        category: str | None = None,
        unit: str | None = None,
    ) -> IngestionResult:
        """
        Ingest material data from an external product URL.

        Fetches product data, deduplicates against existing materials,
        and creates or updates the material record.

        Args:
            url: Product page URL.
            category: Optional material category override.
            unit: Optional unit of measure override.

        Returns:
            IngestionResult with the material and metadata.

        Raises:
            SRGError: If no fetcher supports the URL or fetching fails.
        """
        from src.core.exceptions import CatalogError

        # Find a fetcher that supports this URL
        fetcher = self._find_fetcher(url)
        if fetcher is None:
            raise CatalogError(
                f"No fetcher supports the URL: {url}",
                code="UNSUPPORTED_URL",
            )

        # Fetch product data
        page_data = await fetcher.fetch(url)
        logger.info(
            "product_data_fetched",
            url=url,
            title=page_data.title,
            brand=page_data.brand,
            origin=page_data.origin_country,
        )

        # Normalize the name
        normalized = self._normalize_name(page_data.title)

        # Check for existing material by normalized name
        existing = await self._material_store.find_by_normalized_name(normalized)

        synonyms_added: list[str] = []

        if existing is not None:
            # Update existing material with new data
            existing.source_url = page_data.source_url
            existing.brand = page_data.brand or existing.brand
            existing.description = page_data.description or existing.description
            existing.origin_country = page_data.origin_country or existing.origin_country
            existing.origin_confidence = page_data.origin_confidence
            existing.evidence_text = page_data.evidence_text or existing.evidence_text
            if category:
                existing.category = category
            if unit:
                existing.unit = unit

            material = await self._material_store.update_material(existing)

            # Add new synonyms
            synonyms_added = await self._add_new_synonyms(
                material.id or "", page_data.suggested_synonyms, material.synonyms
            )

            logger.info("material_updated_from_ingestion", material_id=material.id)
            return IngestionResult(
                material=material,
                page_data=page_data,
                created=False,
                synonyms_added=synonyms_added,
            )

        # Create new material
        material = Material(
            name=page_data.title,
            normalized_name=normalized,
            category=category or page_data.category,
            unit=unit,
            description=page_data.description,
            brand=page_data.brand,
            source_url=page_data.source_url,
            origin_country=page_data.origin_country,
            origin_confidence=page_data.origin_confidence,
            evidence_text=page_data.evidence_text,
        )

        material = await self._material_store.create_material(material)

        # Add synonyms
        synonyms_added = await self._add_new_synonyms(
            material.id or "", page_data.suggested_synonyms, []
        )

        logger.info("material_created_from_ingestion", material_id=material.id)
        return IngestionResult(
            material=material,
            page_data=page_data,
            created=True,
            synonyms_added=synonyms_added,
        )

    def _find_fetcher(self, url: str) -> IProductPageFetcher | None:
        """Find a fetcher that supports the given URL."""
        for fetcher in self._fetchers:
            if fetcher.supports_url(url):
                return fetcher
        return None

    def _normalize_name(self, name: str) -> str:
        """Normalize a product name for deduplication."""
        # Strip, lowercase, collapse whitespace
        result = name.strip().lower()
        result = re.sub(r"\s+", " ", result)
        return result

    async def _add_new_synonyms(
        self,
        material_id: str,
        suggested: list[str],
        existing: list[str],
    ) -> list[str]:
        """Add synonyms that don't already exist."""
        existing_lower = {s.lower() for s in existing}
        added: list[str] = []
        for syn in suggested:
            if syn.strip().lower() not in existing_lower:
                await self._material_store.add_synonym(material_id, syn)
                added.append(syn)
        return added
