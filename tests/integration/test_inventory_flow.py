"""Integration test for full inventory → sales flow."""

from datetime import date
from unittest.mock import AsyncMock

from src.application.dto.requests import (
    CreateSalesInvoiceRequest,
    CreateSalesItemRequest,
    ReceiveStockRequest,
)
from src.application.use_cases.create_sales_invoice import CreateSalesInvoiceUseCase
from src.application.use_cases.receive_stock import ReceiveStockUseCase
from src.core.entities.inventory import InventoryItem, MovementType, StockMovement
from src.core.entities.material import Material


class TestInventoryFlow:
    """Full flow: receive stock → sell → verify remaining stock + profit."""

    async def test_receive_then_sell_flow(self):
        """Test complete inventory flow with mocked stores."""
        # Setup mock stores
        inv_store = AsyncMock()
        mat_store = AsyncMock()
        sales_store = AsyncMock()

        # Material exists
        mat_store.get_by_id.return_value = Material(
            id="MAT-001", name="Cable 3x2.5mm", normalized_name="cable 3x2.5mm",
        )

        # Step 1: Receive 100 units at 10.0 each
        inv_item = InventoryItem(id=1, material_id="MAT-001")
        inv_store.get_item_by_material.return_value = None  # First time
        inv_store.create_item.return_value = inv_item
        inv_store.update_item.side_effect = lambda item: item
        inv_store.add_movement.return_value = StockMovement(
            id=1, inventory_item_id=1, movement_type=MovementType.IN,
            quantity=100, unit_cost=10.0, movement_date=date.today(),
        )

        receive_uc = ReceiveStockUseCase(
            inventory_store=inv_store, material_store=mat_store,
        )
        receive_req = ReceiveStockRequest(
            material_id="MAT-001", quantity=100, unit_cost=10.0,
        )
        receive_result = await receive_uc.execute(receive_req)
        assert receive_result.created is True
        assert receive_result.inventory_item.quantity_on_hand == 100.0
        assert receive_result.inventory_item.avg_cost == 10.0

        # Step 2: Sell 30 units at 15.0 each
        # Now inventory has 100 units
        sold_item = InventoryItem(
            id=1, material_id="MAT-001", quantity_on_hand=100.0, avg_cost=10.0,
        )
        inv_store.get_item_by_material.return_value = sold_item

        async def capture_create(inv):
            inv.id = 1
            for i, it in enumerate(inv.items):
                it.id = i + 1
            return inv
        sales_store.create_invoice.side_effect = capture_create

        sell_uc = CreateSalesInvoiceUseCase(
            inventory_store=inv_store, sales_store=sales_store,
        )
        sell_req = CreateSalesInvoiceRequest(
            invoice_number="LS-001",
            customer_name="Customer A",
            items=[
                CreateSalesItemRequest(
                    material_id="MAT-001",
                    description="Cable 3x2.5mm",
                    quantity=30.0,
                    unit_price=15.0,
                ),
            ],
        )
        sell_result = await sell_uc.execute(sell_req)

        # Verify profit
        invoice = sell_result.invoice
        # cost_basis = 10.0 * 30 = 300, line_total = 15 * 30 = 450
        assert invoice.items[0].cost_basis == 300.0
        assert invoice.items[0].line_total == 450.0
        assert invoice.items[0].profit == 150.0
        assert invoice.total_profit == 150.0

        # Verify stock deducted
        updated_item = inv_store.update_item.call_args[0][0]
        assert updated_item.quantity_on_hand == 70.0
