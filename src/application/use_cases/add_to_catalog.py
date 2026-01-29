"""
Add to Catalog Use Case.

Creates or updates materials from invoice line items.
"""

from dataclasses import dataclass, field

from src.application.dto.requests import AddToCatalogRequest
from src.application.dto.responses import (
    AddToCatalogResponse,
    DuplicateWarningResponse,
    MaterialResponse,
)
from src.config import get_logger
from src.core.entities.invoice import RowType
from src.core.entities.material import Material
from src.core.exceptions import InvoiceNotFoundError
from src.core.interfaces.storage import IInvoiceStore, IMaterialStore, IPriceHistoryStore
from src.core.services.catalog_matcher import CatalogMatcher, MatchCandidate

logger = get_logger(__name__)


@dataclass
class AutoMatchResult:
    """Result of automatic catalog matching (no material creation)."""

    matched: int = 0
    unmatched: int = 0
    matches: list[tuple[int, str]] = field(default_factory=list)
    """List of (item_id, material_id) pairs for matched items."""
    candidates: dict[int, list[MatchCandidate]] = field(default_factory=dict)
    """Mapping of item_id -> list of scored match candidates."""


@dataclass
class DuplicateWarning:
    """Warning about a near-duplicate material found during creation."""

    new_material_name: str
    existing_material_id: str
    existing_material_name: str
    similarity_score: float


@dataclass
class AddToCatalogResult:
    """Result of the add-to-catalog operation."""

    materials_created: int = 0
    materials_updated: int = 0
    materials: list[Material] = field(default_factory=list)
    duplicate_warnings: list[DuplicateWarning] = field(default_factory=list)


class AddToCatalogUseCase:
    """
    Use case for adding invoice items to the materials catalog.

    Flow:
    1. Load invoice by ID
    2. Filter line items
    3. For each item, find or create material
    4. Link price history
    """

    def __init__(
        self,
        invoice_store: IInvoiceStore | None = None,
        material_store: IMaterialStore | None = None,
        price_store: IPriceHistoryStore | None = None,
        catalog_matcher: CatalogMatcher | None = None,
    ):
        self._invoice_store = invoice_store
        self._material_store = material_store
        self._price_store = price_store
        self._catalog_matcher = catalog_matcher

    async def _get_invoice_store(self) -> IInvoiceStore:
        if self._invoice_store is None:
            from src.infrastructure.storage.sqlite import get_invoice_store

            self._invoice_store = await get_invoice_store()
        return self._invoice_store

    async def _get_material_store(self) -> IMaterialStore:
        if self._material_store is None:
            from src.infrastructure.storage.sqlite import get_material_store

            self._material_store = await get_material_store()
        return self._material_store

    async def _get_price_store(self) -> IPriceHistoryStore:
        if self._price_store is None:
            from src.infrastructure.storage.sqlite import get_price_history_store

            self._price_store = await get_price_history_store()
        return self._price_store

    async def _get_catalog_matcher(self) -> CatalogMatcher:
        if self._catalog_matcher is None:
            mat_store = await self._get_material_store()
            self._catalog_matcher = CatalogMatcher(material_store=mat_store)
        return self._catalog_matcher

    async def auto_match_items(self, invoice_id: int) -> AutoMatchResult:
        """
        Automatically match invoice line items to existing materials.

        Uses the CatalogMatcher to find scored candidates for each item.
        If a single exact match (score 1.0) is found, it is auto-linked.
        Otherwise, candidates are returned for manual selection.

        Unlike execute(), this method only matches -- it never creates new
        materials. Unmatched items remain with needs_catalog=True.

        Args:
            invoice_id: Invoice whose items to match.

        Returns:
            AutoMatchResult with match/unmatch counts, matched pairs,
            and scored candidates per item.
        """
        logger.info("auto_match_started", invoice_id=invoice_id)

        inv_store = await self._get_invoice_store()
        price_store = await self._get_price_store()
        matcher = await self._get_catalog_matcher()

        invoice = await inv_store.get_invoice(invoice_id)
        if invoice is None:
            logger.warning("auto_match_invoice_not_found", invoice_id=invoice_id)
            return AutoMatchResult()

        items = [i for i in invoice.items if i.row_type == RowType.LINE_ITEM]
        result = AutoMatchResult()

        for item in items:
            normalized = item.item_name.strip().lower()
            if not normalized:
                result.unmatched += 1
                continue

            # Use the CatalogMatcher for scored candidates
            candidates = await matcher.find_matches(item.item_name, top_k=5)
            item_id = item.id or 0
            result.candidates[item_id] = candidates

            # Auto-link if there is a single exact match
            if candidates and candidates[0].score == 1.0:
                best = candidates[0]
                if item.id is not None:
                    await inv_store.update_item_material_id(item.id, best.material_id)
                    await price_store.link_material(best.material_id, normalized)
                result.matched += 1
                result.matches.append((item_id, best.material_id))
            else:
                result.unmatched += 1

        logger.info(
            "auto_match_complete",
            invoice_id=invoice_id,
            matched=result.matched,
            unmatched=result.unmatched,
        )
        return result

    async def execute(self, request: AddToCatalogRequest) -> AddToCatalogResult:
        """Execute the add-to-catalog use case."""
        logger.info("add_to_catalog_started", invoice_id=request.invoice_id)

        inv_store = await self._get_invoice_store()
        mat_store = await self._get_material_store()
        price_store = await self._get_price_store()
        matcher = await self._get_catalog_matcher()

        # 1. Get invoice
        invoice = await inv_store.get_invoice(request.invoice_id)
        if invoice is None:
            raise InvoiceNotFoundError(request.invoice_id)

        # 2. Filter items
        items = [i for i in invoice.items if i.row_type == RowType.LINE_ITEM]
        if request.item_ids is not None:
            items = [i for i in items if i.id in request.item_ids]

        result = AddToCatalogResult()

        # 3. Process each item
        for item in items:
            normalized = item.item_name.strip().lower()
            if not normalized:
                continue

            # Check if material already exists
            existing = await mat_store.find_by_normalized_name(normalized)
            if existing is None:
                existing = await mat_store.find_by_synonym(normalized)

            if existing is not None:
                # Update existing material - add synonym if item_name differs
                if normalized not in [s.lower() for s in existing.synonyms] and normalized != existing.normalized_name:
                    await mat_store.add_synonym(existing.id, item.item_name)  # type: ignore[arg-type]

                # Update hs_code/unit if missing
                changed = False
                if not existing.hs_code and item.hs_code:
                    existing.hs_code = item.hs_code
                    changed = True
                if not existing.unit and item.unit:
                    existing.unit = item.unit
                    changed = True
                if changed:
                    await mat_store.update_material(existing)

                result.materials_updated += 1
                result.materials.append(existing)
            else:
                # Check for near-duplicates before creating
                duplicate = await matcher.check_duplicate(item.item_name)
                if duplicate is not None:
                    logger.warning(
                        "near_duplicate_detected",
                        new_name=item.item_name,
                        existing_id=duplicate.material_id,
                        existing_name=duplicate.material_name,
                        score=duplicate.score,
                    )
                    result.duplicate_warnings.append(
                        DuplicateWarning(
                            new_material_name=item.item_name,
                            existing_material_id=duplicate.material_id,
                            existing_material_name=duplicate.material_name,
                            similarity_score=duplicate.score,
                        )
                    )

                # Create new material (do NOT block creation)
                material = Material(
                    name=item.item_name,
                    normalized_name=normalized,
                    hs_code=item.hs_code,
                    unit=item.unit,
                )
                material = await mat_store.create_material(material)
                result.materials_created += 1
                result.materials.append(material)

            # Link price history and mark invoice item
            mat = result.materials[-1]
            await price_store.link_material(mat.id, normalized)  # type: ignore[arg-type]
            if item.id is not None and mat.id is not None:
                await inv_store.update_item_material_id(item.id, mat.id)

        logger.info(
            "add_to_catalog_complete",
            created=result.materials_created,
            updated=result.materials_updated,
            duplicate_warnings=len(result.duplicate_warnings),
        )
        return result

    def to_response(self, result: AddToCatalogResult) -> AddToCatalogResponse:
        """Convert result to API response."""
        return AddToCatalogResponse(
            materials_created=result.materials_created,
            materials_updated=result.materials_updated,
            materials=[
                MaterialResponse(
                    id=m.id or "",
                    name=m.name,
                    normalized_name=m.normalized_name,
                    hs_code=m.hs_code,
                    category=m.category,
                    unit=m.unit,
                    description=m.description,
                    synonyms=[],
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
                for m in result.materials
            ],
            duplicate_warnings=[
                DuplicateWarningResponse(
                    new_material_name=w.new_material_name,
                    existing_material_id=w.existing_material_id,
                    existing_material_name=w.existing_material_name,
                    similarity_score=w.similarity_score,
                )
                for w in result.duplicate_warnings
            ],
        )
