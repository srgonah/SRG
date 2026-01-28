"""Create Sales Invoice Use Case — deducts stock and computes profit."""

from dataclasses import dataclass
from datetime import date, datetime

from src.application.dto.requests import CreateSalesInvoiceRequest
from src.application.dto.responses import (
    LocalSalesInvoiceResponse,
    LocalSalesItemResponse,
)
from src.config import get_logger
from src.core.entities.inventory import MovementType, StockMovement
from src.core.entities.local_sale import LocalSalesInvoice, LocalSalesItem
from src.core.exceptions import InsufficientStockError, InventoryItemNotFoundError
from src.core.interfaces.inventory_store import IInventoryStore
from src.core.interfaces.sales_store import ISalesStore

logger = get_logger(__name__)


@dataclass
class CreateSalesInvoiceResult:
    """Result of creating a sales invoice."""

    invoice: LocalSalesInvoice


class CreateSalesInvoiceUseCase:
    """Create a local sales invoice, deduct stock, and compute profit."""

    def __init__(
        self,
        inventory_store: IInventoryStore | None = None,
        sales_store: ISalesStore | None = None,
    ):
        self._inventory_store = inventory_store
        self._sales_store = sales_store

    async def _get_inventory_store(self) -> IInventoryStore:
        if self._inventory_store is None:
            from src.infrastructure.storage.sqlite import get_inventory_store

            self._inventory_store = await get_inventory_store()
        return self._inventory_store

    async def _get_sales_store(self) -> ISalesStore:
        if self._sales_store is None:
            from src.infrastructure.storage.sqlite import get_sales_store

            self._sales_store = await get_sales_store()
        return self._sales_store

    async def execute(
        self, request: CreateSalesInvoiceRequest
    ) -> CreateSalesInvoiceResult:
        """Execute create sales invoice use case."""
        logger.info(
            "create_sales_invoice_started",
            invoice_number=request.invoice_number,
            items=len(request.items),
        )

        inv_store = await self._get_inventory_store()
        sales_store = await self._get_sales_store()

        sale_date = (
            date.fromisoformat(request.sale_date)
            if request.sale_date
            else date.today()
        )
        now = datetime.utcnow()

        sales_items: list[LocalSalesItem] = []

        for item_req in request.items:
            # Get inventory item
            inv_item = await inv_store.get_item_by_material(item_req.material_id)
            if inv_item is None:
                raise InventoryItemNotFoundError(0)

            # Check sufficient stock
            if inv_item.quantity_on_hand < item_req.quantity:
                raise InsufficientStockError(
                    material_id=item_req.material_id,
                    requested=item_req.quantity,
                    available=inv_item.quantity_on_hand,
                )

            # Calculate cost basis
            cost_basis = inv_item.avg_cost * item_req.quantity

            # Deduct stock
            inv_item.quantity_on_hand -= item_req.quantity
            inv_item.last_movement_date = sale_date
            await inv_store.update_item(inv_item)

            # Record OUT movement
            movement = StockMovement(
                inventory_item_id=inv_item.id,  # type: ignore[arg-type]
                movement_type=MovementType.OUT,
                quantity=item_req.quantity,
                unit_cost=inv_item.avg_cost,
                reference=request.invoice_number,
                notes=f"Sale to {request.customer_name}",
                movement_date=sale_date,
                created_at=now,
            )
            await inv_store.add_movement(movement)

            # Build sales item
            sales_item = LocalSalesItem(
                inventory_item_id=inv_item.id,  # type: ignore[arg-type]
                material_id=item_req.material_id,
                description=item_req.description,
                quantity=item_req.quantity,
                unit_price=item_req.unit_price,
                cost_basis=cost_basis,
                created_at=now,
            )
            sales_items.append(sales_item)

        # Build invoice (model_validator computes totals)
        invoice = LocalSalesInvoice(
            invoice_number=request.invoice_number,
            customer_name=request.customer_name,
            sale_date=sale_date,
            tax_amount=request.tax_amount,
            notes=request.notes,
            items=sales_items,
            created_at=now,
            updated_at=now,
        )

        # Persist
        invoice = await sales_store.create_invoice(invoice)

        logger.info(
            "create_sales_invoice_complete",
            invoice_id=invoice.id,
            total=invoice.total_amount,
            profit=invoice.total_profit,
        )

        return CreateSalesInvoiceResult(invoice=invoice)

    def to_response(
        self, result: CreateSalesInvoiceResult
    ) -> LocalSalesInvoiceResponse:
        """Convert result to API response."""
        inv = result.invoice
        return LocalSalesInvoiceResponse(
            id=inv.id,  # type: ignore[arg-type]
            invoice_number=inv.invoice_number,
            customer_name=inv.customer_name,
            sale_date=inv.sale_date,
            subtotal=inv.subtotal,
            tax_amount=inv.tax_amount,
            total_amount=inv.total_amount,
            total_cost=inv.total_cost,
            total_profit=inv.total_profit,
            notes=inv.notes,
            items=[
                LocalSalesItemResponse(
                    id=item.id,  # type: ignore[arg-type]
                    inventory_item_id=item.inventory_item_id,
                    material_id=item.material_id,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    cost_basis=item.cost_basis,
                    line_total=item.line_total,
                    profit=item.profit,
                )
                for item in inv.items
            ],
            created_at=inv.created_at,
        )
