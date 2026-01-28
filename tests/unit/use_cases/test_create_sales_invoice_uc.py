"""Tests for CreateSalesInvoiceUseCase."""

from unittest.mock import AsyncMock

import pytest

from src.application.dto.requests import CreateSalesInvoiceRequest, CreateSalesItemRequest
from src.application.use_cases.create_sales_invoice import CreateSalesInvoiceUseCase
from src.core.entities.inventory import InventoryItem
from src.core.exceptions import InsufficientStockError, InventoryItemNotFoundError


@pytest.fixture
def mock_inventory_store():
    return AsyncMock()


@pytest.fixture
def mock_sales_store():
    return AsyncMock()


@pytest.fixture
def use_case(mock_inventory_store, mock_sales_store):
    return CreateSalesInvoiceUseCase(
        inventory_store=mock_inventory_store,
        sales_store=mock_sales_store,
    )


class TestCreateSalesInvoiceUseCase:
    async def test_full_invoice_creation(self, use_case, mock_inventory_store, mock_sales_store):
        """Test creating a full invoice with stock deduction."""
        item = InventoryItem(
            id=1, material_id="MAT-001", quantity_on_hand=100.0, avg_cost=10.0,
        )
        mock_inventory_store.get_item_by_material.return_value = item
        mock_inventory_store.update_item.return_value = item
        mock_inventory_store.add_movement.return_value = AsyncMock()

        # Sales store returns what was passed in (simulate)
        async def create_inv(inv):
            inv.id = 1
            for i, it in enumerate(inv.items):
                it.id = i + 1
            return inv
        mock_sales_store.create_invoice.side_effect = create_inv

        request = CreateSalesInvoiceRequest(
            invoice_number="LS-001",
            customer_name="Test Customer",
            items=[
                CreateSalesItemRequest(
                    material_id="MAT-001",
                    description="Cable",
                    quantity=10.0,
                    unit_price=15.0,
                ),
            ],
        )
        result = await use_case.execute(request)
        assert result.invoice.invoice_number == "LS-001"
        mock_sales_store.create_invoice.assert_called_once()

    async def test_stock_deducted(self, use_case, mock_inventory_store, mock_sales_store):
        """Test that stock is deducted for each item."""
        item = InventoryItem(
            id=1, material_id="MAT-001", quantity_on_hand=100.0, avg_cost=10.0,
        )
        mock_inventory_store.get_item_by_material.return_value = item
        mock_inventory_store.update_item.return_value = item
        mock_inventory_store.add_movement.return_value = AsyncMock()
        mock_sales_store.create_invoice.side_effect = lambda inv: inv

        request = CreateSalesInvoiceRequest(
            invoice_number="LS-002",
            customer_name="Test",
            items=[
                CreateSalesItemRequest(
                    material_id="MAT-001", description="Cable",
                    quantity=30.0, unit_price=15.0,
                ),
            ],
        )
        await use_case.execute(request)
        # Stock should have been deducted
        updated = mock_inventory_store.update_item.call_args[0][0]
        assert updated.quantity_on_hand == 70.0

    async def test_profit_calculation(self, use_case, mock_inventory_store, mock_sales_store):
        """Test profit = selling price - cost."""
        item = InventoryItem(
            id=1, material_id="MAT-001", quantity_on_hand=100.0, avg_cost=10.0,
        )
        mock_inventory_store.get_item_by_material.return_value = item
        mock_inventory_store.update_item.return_value = item
        mock_inventory_store.add_movement.return_value = AsyncMock()

        saved_invoice = None
        async def capture_inv(inv):
            nonlocal saved_invoice
            saved_invoice = inv
            inv.id = 1
            return inv
        mock_sales_store.create_invoice.side_effect = capture_inv

        request = CreateSalesInvoiceRequest(
            invoice_number="LS-003",
            customer_name="Test",
            items=[
                CreateSalesItemRequest(
                    material_id="MAT-001", description="Cable",
                    quantity=10.0, unit_price=15.0,
                ),
            ],
        )
        await use_case.execute(request)
        # cost_basis = 10.0 * 10 = 100, line_total = 15 * 10 = 150, profit = 50
        assert saved_invoice is not None
        assert saved_invoice.items[0].cost_basis == 100.0

    async def test_insufficient_stock_error(self, use_case, mock_inventory_store):
        """Test error when not enough stock."""
        item = InventoryItem(
            id=1, material_id="MAT-001", quantity_on_hand=5.0, avg_cost=10.0,
        )
        mock_inventory_store.get_item_by_material.return_value = item

        request = CreateSalesInvoiceRequest(
            invoice_number="LS-004",
            customer_name="Test",
            items=[
                CreateSalesItemRequest(
                    material_id="MAT-001", description="Cable",
                    quantity=50.0, unit_price=15.0,
                ),
            ],
        )
        with pytest.raises(InsufficientStockError):
            await use_case.execute(request)

    async def test_item_not_found_error(self, use_case, mock_inventory_store):
        """Test error when inventory item not found."""
        mock_inventory_store.get_item_by_material.return_value = None

        request = CreateSalesInvoiceRequest(
            invoice_number="LS-005",
            customer_name="Test",
            items=[
                CreateSalesItemRequest(
                    material_id="NONEXISTENT", description="Item",
                    quantity=1.0, unit_price=10.0,
                ),
            ],
        )
        with pytest.raises(InventoryItemNotFoundError):
            await use_case.execute(request)
