"""
Amazon Import Service.

Imports materials from Amazon search results with deduplication
against existing catalog entries.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.config import get_logger
from src.core.entities.material import Material, OriginConfidence
from src.core.interfaces.material_store import IMaterialStore

logger = get_logger(__name__)


@dataclass
class ImportedItem:
    """Represents an imported item with its status."""

    asin: str
    title: str
    brand: str | None
    price: str | None
    price_value: float | None
    currency: str | None
    product_url: str
    status: str  # "saved", "skipped_duplicate", "error"
    material_id: str | None = None
    error_message: str | None = None
    existing_material_id: str | None = None  # If duplicate


@dataclass
class ImportResult:
    """Result of an Amazon import operation."""

    items_found: int
    items_saved: int
    items_skipped: int
    items_error: int
    items: list[ImportedItem] = field(default_factory=list)


class AmazonImportService:
    """
    Service for importing materials from Amazon search results.

    Handles:
    - Deduplication by normalized_name and synonyms
    - Material creation with proper origin confidence
    - Reference price tracking
    """

    def __init__(self, material_store: IMaterialStore):
        self._store = material_store

    async def import_items(
        self,
        search_results: list,
        category: str | None = None,
        unit: str | None = None,
    ) -> ImportResult:
        """
        Import Amazon search results into the materials catalog.

        Args:
            search_results: List of AmazonSearchResult objects
            category: Category to assign to imported materials
            unit: Unit to assign to imported materials

        Returns:
            ImportResult with counts and item details
        """
        result = ImportResult(
            items_found=len(search_results),
            items_saved=0,
            items_skipped=0,
            items_error=0,
        )

        for item in search_results:
            imported = await self._process_item(item, category, unit)
            result.items.append(imported)

            if imported.status == "saved":
                result.items_saved += 1
            elif imported.status == "skipped_duplicate":
                result.items_skipped += 1
            else:
                result.items_error += 1

        logger.info(
            "amazon_import_complete",
            found=result.items_found,
            saved=result.items_saved,
            skipped=result.items_skipped,
            errors=result.items_error,
        )

        return result

    async def _process_item(
        self,
        item,
        category: str | None,
        unit: str | None,
    ) -> ImportedItem:
        """Process a single search result item."""
        try:
            # Normalize the title for deduplication
            normalized_name = item.title.strip().lower()

            # Check for existing material by normalized name
            existing = await self._store.find_by_normalized_name(normalized_name)
            if existing:
                logger.debug(
                    "item_duplicate_by_name",
                    asin=item.asin,
                    existing_id=existing.id,
                )
                return ImportedItem(
                    asin=item.asin,
                    title=item.title,
                    brand=item.brand,
                    price=item.price,
                    price_value=item.price_value,
                    currency=item.currency,
                    product_url=item.product_url,
                    status="skipped_duplicate",
                    existing_material_id=existing.id,
                )

            # Check for existing material by synonym (title as synonym)
            existing_by_syn = await self._store.find_by_synonym(item.title)
            if existing_by_syn:
                logger.debug(
                    "item_duplicate_by_synonym",
                    asin=item.asin,
                    existing_id=existing_by_syn.id,
                )
                return ImportedItem(
                    asin=item.asin,
                    title=item.title,
                    brand=item.brand,
                    price=item.price,
                    price_value=item.price_value,
                    currency=item.currency,
                    product_url=item.product_url,
                    status="skipped_duplicate",
                    existing_material_id=existing_by_syn.id,
                )

            # Check by brand+simplified name pattern
            if item.brand:
                brand_pattern = f"{item.brand} ".lower()
                if normalized_name.startswith(brand_pattern):
                    simplified = normalized_name[len(brand_pattern):].strip()
                    if simplified:
                        existing_simplified = await self._store.find_by_normalized_name(
                            simplified
                        )
                        if existing_simplified:
                            logger.debug(
                                "item_duplicate_by_simplified",
                                asin=item.asin,
                                existing_id=existing_simplified.id,
                            )
                            return ImportedItem(
                                asin=item.asin,
                                title=item.title,
                                brand=item.brand,
                                price=item.price,
                                price_value=item.price_value,
                                currency=item.currency,
                                product_url=item.product_url,
                                status="skipped_duplicate",
                                existing_material_id=existing_simplified.id,
                            )

            # Create new material
            # Origin: We don't guess - mark as unknown
            material = Material(
                name=item.title,
                normalized_name=normalized_name,
                category=category,
                unit=unit,
                brand=item.brand,
                source_url=item.product_url,
                origin_country=None,  # Don't guess
                origin_confidence=OriginConfidence.UNKNOWN,
                description=self._build_description(item),
            )

            created = await self._store.create_material(material)

            # Add brand as synonym if present
            if item.brand and item.brand.lower() != normalized_name:
                try:
                    await self._store.add_synonym(created.id, item.brand)
                except Exception:
                    pass  # Non-critical

            logger.info(
                "material_imported",
                asin=item.asin,
                material_id=created.id,
                name=created.name[:50],
            )

            return ImportedItem(
                asin=item.asin,
                title=item.title,
                brand=item.brand,
                price=item.price,
                price_value=item.price_value,
                currency=item.currency,
                product_url=item.product_url,
                status="saved",
                material_id=created.id,
            )

        except Exception as e:
            logger.error(
                "item_import_error",
                asin=item.asin,
                error=str(e),
            )
            return ImportedItem(
                asin=item.asin,
                title=item.title,
                brand=item.brand,
                price=item.price,
                price_value=item.price_value,
                currency=item.currency,
                product_url=item.product_url,
                status="error",
                error_message=str(e),
            )

    @staticmethod
    def _build_description(item) -> str | None:
        """Build a description from item metadata."""
        parts = []
        if item.brand:
            parts.append(f"Brand: {item.brand}")
        if item.price:
            parts.append(f"Reference price: {item.price}")
        if item.rating:
            parts.append(f"Rating: {item.rating}/5")
        if item.reviews_count:
            parts.append(f"Reviews: {item.reviews_count}")
        return " | ".join(parts) if parts else None
