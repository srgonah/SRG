"""
Add to Catalog Use Case.

Creates or updates materials from invoice line items.
"""

from dataclasses import dataclass, field

from src.application.dto.requests import AddToCatalogRequest
from src.application.dto.responses import (
    AddToCatalogResponse,
    MaterialResponse,
)
from src.config import get_logger
from src.core.entities.invoice import RowType
from src.core.entities.material import Material
from src.core.exceptions import InvoiceNotFoundError
from src.core.interfaces.storage import IInvoiceStore, IMaterialStore, IPriceHistoryStore

logger = get_logger(__name__)


@dataclass
class AutoMatchResult:
    """Result of automatic catalog matching (no material creation)."""

    matched: int = 0
    unmatched: int = 0
    matches: list[tuple[int, str]] = field(default_factory=list)
    """List of (item_id, material_id) pairs for matched items."""


@dataclass
class AddToCatalogResult:
    """Result of the add-to-catalog operation."""

    materials_created: int = 0
    materials_updated: int = 0
    materials: list[Material] = field(default_factory=list)


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
    ):
        self._invoice_store = invoice_store
        self._material_store = material_store
        self._price_store = price_store

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

    async def auto_match_items(self, invoice_id: int) -> AutoMatchResult:
        """
        Automatically match invoice line items to existing materials.

        Unlike execute(), this method only matches — it never creates new
        materials. Unmatched items remain with needs_catalog=True.

        Args:
            invoice_id: Invoice whose items to match.

        Returns:
            AutoMatchResult with match/unmatch counts and matched pairs.
        """
        logger.info("auto_match_started", invoice_id=invoice_id)

        inv_store = await self._get_invoice_store()
        mat_store = await self._get_material_store()
        price_store = await self._get_price_store()

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

            # Try to find existing material
            existing = await mat_store.find_by_normalized_name(normalized)
            if existing is None:
                existing = await mat_store.find_by_synonym(normalized)

            if existing is not None and existing.id is not None:
                # Match found — link item to material
                if item.id is not None:
                    await inv_store.update_item_material_id(item.id, existing.id)
                    await price_store.link_material(existing.id, normalized)
                result.matched += 1
                result.matches.append((item.id or 0, existing.id))
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
                # Create new material
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
        )
