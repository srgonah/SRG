"""Issue Stock Use Case — OUT movement with balance check."""

from dataclasses import dataclass
from datetime import date, datetime

from src.application.dto.requests import IssueStockRequest
from src.application.dto.responses import (
    InventoryItemResponse,
    IssueStockResponse,
    StockMovementResponse,
)
from src.config import get_logger
from src.core.entities.inventory import MovementType, StockMovement
from src.core.exceptions import InsufficientStockError, InventoryItemNotFoundError
from src.core.interfaces.inventory_store import IInventoryStore

logger = get_logger(__name__)


@dataclass
class IssueStockResult:
    """Result of issuing stock."""

    inventory_item: object  # InventoryItem
    movement: StockMovement


class IssueStockUseCase:
    """Issue stock (OUT movement) with balance check."""

    def __init__(
        self,
        inventory_store: IInventoryStore | None = None,
    ):
        self._inventory_store = inventory_store

    async def _get_inventory_store(self) -> IInventoryStore:
        if self._inventory_store is None:
            from src.infrastructure.storage.sqlite import get_inventory_store

            self._inventory_store = await get_inventory_store()
        return self._inventory_store

    async def execute(self, request: IssueStockRequest) -> IssueStockResult:
        """Execute issue stock use case."""
        logger.info(
            "issue_stock_started",
            material_id=request.material_id,
            quantity=request.quantity,
        )

        inv_store = await self._get_inventory_store()

        # 1. Get inventory item by material_id
        inv_item = await inv_store.get_item_by_material(request.material_id)
        if inv_item is None:
            raise InventoryItemNotFoundError(0)

        # 2. Check sufficient stock
        if inv_item.quantity_on_hand < request.quantity:
            raise InsufficientStockError(
                material_id=request.material_id,
                requested=request.quantity,
                available=inv_item.quantity_on_hand,
            )

        # 3. Deduct stock (avg_cost unchanged)
        movement_date = (
            date.fromisoformat(request.movement_date)
            if request.movement_date
            else date.today()
        )
        inv_item.quantity_on_hand -= request.quantity
        inv_item.last_movement_date = movement_date
        inv_item = await inv_store.update_item(inv_item)

        # 4. Record OUT movement
        movement = StockMovement(
            inventory_item_id=inv_item.id,  # type: ignore[arg-type]
            movement_type=MovementType.OUT,
            quantity=request.quantity,
            unit_cost=inv_item.avg_cost,
            reference=request.reference,
            notes=request.notes,
            movement_date=movement_date,
            created_at=datetime.utcnow(),
        )
        movement = await inv_store.add_movement(movement)

        logger.info(
            "issue_stock_complete",
            item_id=inv_item.id,
            remaining_qty=inv_item.quantity_on_hand,
        )

        return IssueStockResult(
            inventory_item=inv_item,
            movement=movement,
        )

    def to_response(self, result: IssueStockResult) -> IssueStockResponse:
        """Convert result to API response."""
        from src.core.entities.inventory import InventoryItem

        item: InventoryItem = result.inventory_item  # type: ignore[assignment]
        mvmt = result.movement
        return IssueStockResponse(
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
        )
