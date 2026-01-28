"""Inventory management endpoints."""

from fastapi import APIRouter, Depends, status

from src.api.dependencies import (
    get_inv_item_store,
    get_issue_stock_use_case,
    get_receive_stock_use_case,
)
from src.application.dto.requests import IssueStockRequest, ReceiveStockRequest
from src.application.dto.responses import (
    ErrorResponse,
    InventoryItemResponse,
    InventoryStatusResponse,
    IssueStockResponse,
    ReceiveStockResponse,
    StockMovementResponse,
)
from src.application.use_cases.issue_stock import IssueStockUseCase
from src.application.use_cases.receive_stock import ReceiveStockUseCase
from src.infrastructure.storage.sqlite import SQLiteInventoryStore

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.post(
    "/receive",
    response_model=ReceiveStockResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def receive_stock(
    request: ReceiveStockRequest,
    use_case: ReceiveStockUseCase = Depends(get_receive_stock_use_case),
) -> ReceiveStockResponse:
    """Receive stock (IN movement) with WAC recalculation."""
    result = await use_case.execute(request)
    return use_case.to_response(result)


@router.post(
    "/issue",
    response_model=IssueStockResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def issue_stock(
    request: IssueStockRequest,
    use_case: IssueStockUseCase = Depends(get_issue_stock_use_case),
) -> IssueStockResponse:
    """Issue stock (OUT movement) with balance check."""
    result = await use_case.execute(request)
    return use_case.to_response(result)


@router.get(
    "/status",
    response_model=InventoryStatusResponse,
)
async def get_inventory_status(
    limit: int = 100,
    offset: int = 0,
    store: SQLiteInventoryStore = Depends(get_inv_item_store),
) -> InventoryStatusResponse:
    """Get current inventory status for all items."""
    items = await store.list_items(limit=limit, offset=offset)
    return InventoryStatusResponse(
        items=[
            InventoryItemResponse(
                id=item.id,  # type: ignore[arg-type]
                material_id=item.material_id,
                quantity_on_hand=item.quantity_on_hand,
                avg_cost=item.avg_cost,
                total_value=item.total_value,
                last_movement_date=item.last_movement_date,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        total=len(items),
    )


@router.get(
    "/{item_id}/movements",
    response_model=list[StockMovementResponse],
)
async def get_movements(
    item_id: int,
    limit: int = 100,
    store: SQLiteInventoryStore = Depends(get_inv_item_store),
) -> list[StockMovementResponse]:
    """Get stock movements for an inventory item."""
    movements = await store.get_movements(item_id, limit=limit)
    return [
        StockMovementResponse(
            id=m.id,  # type: ignore[arg-type]
            movement_type=m.movement_type.value,
            quantity=m.quantity,
            unit_cost=m.unit_cost,
            reference=m.reference,
            notes=m.notes,
            movement_date=m.movement_date,
            created_at=m.created_at,
        )
        for m in movements
    ]
