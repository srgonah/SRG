"""Receive Stock Use Case — IN movement with WAC recalculation."""

from dataclasses import dataclass
from datetime import date, datetime

from src.application.dto.requests import ReceiveStockRequest
from src.application.dto.responses import (
    InventoryItemResponse,
    ReceiveStockResponse,
    StockMovementResponse,
)
from src.config import get_logger
from src.core.entities.inventory import InventoryItem, MovementType, StockMovement
from src.core.exceptions import MaterialNotFoundError
from src.core.interfaces.inventory_store import IInventoryStore
from src.core.interfaces.material_store import IMaterialStore

logger = get_logger(__name__)


@dataclass
class ReceiveStockResult:
    """Result of receiving stock."""

    inventory_item: InventoryItem
    movement: StockMovement
    created: bool = False  # True if a new inventory item was created


class ReceiveStockUseCase:
    """Receive stock (IN movement) with WAC recalculation."""

    def __init__(
        self,
        inventory_store: IInventoryStore | None = None,
        material_store: IMaterialStore | None = None,
    ):
        self._inventory_store = inventory_store
        self._material_store = material_store

    async def _get_inventory_store(self) -> IInventoryStore:
        if self._inventory_store is None:
            from src.infrastructure.storage.sqlite import get_inventory_store

            self._inventory_store = await get_inventory_store()
        return self._inventory_store

    async def _get_material_store(self) -> IMaterialStore:
        if self._material_store is None:
            from src.infrastructure.storage.sqlite import get_material_store

            self._material_store = await get_material_store()
        return self._material_store

    async def execute(self, request: ReceiveStockRequest) -> ReceiveStockResult:
        """Execute receive stock use case."""
        logger.info(
            "receive_stock_started",
            material_id=request.material_id,
            quantity=request.quantity,
        )

        # 1. Validate material exists
        mat_store = await self._get_material_store()
        material = await mat_store.get_material(request.material_id)
        if material is None:
            raise MaterialNotFoundError(request.material_id)

        inv_store = await self._get_inventory_store()

        # 2. Get or create inventory item
        created = False
        inv_item = await inv_store.get_item_by_material(request.material_id)
        if inv_item is None:
            now = datetime.utcnow()
            inv_item = InventoryItem(
                material_id=request.material_id,
                quantity_on_hand=0.0,
                avg_cost=0.0,
                created_at=now,
                updated_at=now,
            )
            inv_item = await inv_store.create_item(inv_item)
            created = True

        # 3. WAC recalculation
        old_qty = inv_item.quantity_on_hand
        old_avg = inv_item.avg_cost
        new_qty = request.quantity
        new_cost = request.unit_cost

        total_qty = old_qty + new_qty
        if total_qty > 0:
            new_avg = (old_qty * old_avg + new_qty * new_cost) / total_qty
        else:
            new_avg = new_cost

        # 4. Update inventory item
        movement_date = (
            date.fromisoformat(request.movement_date)
            if request.movement_date
            else date.today()
        )
        inv_item.quantity_on_hand = total_qty
        inv_item.avg_cost = new_avg
        inv_item.last_movement_date = movement_date
        inv_item = await inv_store.update_item(inv_item)

        # 5. Record stock movement
        movement = StockMovement(
            inventory_item_id=inv_item.id,  # type: ignore[arg-type]
            movement_type=MovementType.IN,
            quantity=request.quantity,
            unit_cost=request.unit_cost,
            reference=request.reference,
            notes=request.notes,
            movement_date=movement_date,
            created_at=datetime.utcnow(),
        )
        movement = await inv_store.add_movement(movement)

        logger.info(
            "receive_stock_complete",
            item_id=inv_item.id,
            new_qty=inv_item.quantity_on_hand,
            new_avg=round(inv_item.avg_cost, 4),
        )

        return ReceiveStockResult(
            inventory_item=inv_item,
            movement=movement,
            created=created,
        )

    def to_response(self, result: ReceiveStockResult) -> ReceiveStockResponse:
        """Convert result to API response."""
        item = result.inventory_item
        mvmt = result.movement
        return ReceiveStockResponse(
            inventory_item=InventoryItemResponse(
                id=item.id,  # type: ignore[arg-type]
                material_id=item.material_id,
                quantity_on_hand=item.quantity_on_hand,
                avg_cost=item.avg_cost,
                total_value=item.total_value,
                last_movement_date=item.last_movement_date,
                created_at=item.created_at,
                updated_at=item.updated_at,
            ),
            movement=StockMovementResponse(
                id=mvmt.id,  # type: ignore[arg-type]
                movement_type=mvmt.movement_type.value,
                quantity=mvmt.quantity,
                unit_cost=mvmt.unit_cost,
                reference=mvmt.reference,
                notes=mvmt.notes,
                movement_date=mvmt.movement_date,
                created_at=mvmt.created_at,
            ),
            created=result.created,
        )
