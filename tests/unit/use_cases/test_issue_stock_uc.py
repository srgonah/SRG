"""Tests for IssueStockUseCase."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from src.application.dto.requests import IssueStockRequest
from src.application.use_cases.issue_stock import IssueStockUseCase
from src.core.entities.inventory import InventoryItem, MovementType, StockMovement
from src.core.exceptions import InsufficientStockError, InventoryItemNotFoundError


@pytest.fixture
def mock_inventory_store():
    return AsyncMock()


@pytest.fixture
def use_case(mock_inventory_store):
    return IssueStockUseCase(inventory_store=mock_inventory_store)


class TestIssueStockUseCase:
    async def test_successful_issue(self, use_case, mock_inventory_store):
        """Test successful stock issue."""
        item = InventoryItem(
            id=1, material_id="MAT-001", quantity_on_hand=100.0, avg_cost=10.0,
        )
        mock_inventory_store.get_item_by_material.return_value = item
        mock_inventory_store.update_item.return_value = item
        mock_inventory_store.add_movement.return_value = StockMovement(
            id=1, inventory_item_id=1, movement_type=MovementType.OUT,
            quantity=30, unit_cost=10.0, movement_date=date.today(),
        )

        request = IssueStockRequest(material_id="MAT-001", quantity=30)
        await use_case.execute(request)
        updated = mock_inventory_store.update_item.call_args[0][0]
        assert updated.quantity_on_hand == 70.0

    async def test_insufficient_stock(self, use_case, mock_inventory_store):
        """Test error when not enough stock."""
        item = InventoryItem(
            id=1, material_id="MAT-001", quantity_on_hand=10.0, avg_cost=10.0,
        )
        mock_inventory_store.get_item_by_material.return_value = item

        request = IssueStockRequest(material_id="MAT-001", quantity=50)
        with pytest.raises(InsufficientStockError):
            await use_case.execute(request)

    async def test_item_not_found(self, use_case, mock_inventory_store):
        """Test error when inventory item doesn't exist."""
        mock_inventory_store.get_item_by_material.return_value = None

        request = IssueStockRequest(material_id="NONEXISTENT", quantity=10)
        with pytest.raises(InventoryItemNotFoundError):
            await use_case.execute(request)

    async def test_movement_uses_avg_cost(self, use_case, mock_inventory_store):
        """Test that OUT movement uses current avg_cost."""
        item = InventoryItem(
            id=1, material_id="MAT-001", quantity_on_hand=100.0, avg_cost=12.5,
        )
        mock_inventory_store.get_item_by_material.return_value = item
        mock_inventory_store.update_item.return_value = item
        mock_inventory_store.add_movement.return_value = StockMovement(
            id=1, inventory_item_id=1, movement_type=MovementType.OUT,
            quantity=20, unit_cost=12.5, movement_date=date.today(),
        )

        request = IssueStockRequest(material_id="MAT-001", quantity=20)
        await use_case.execute(request)
        mvmt = mock_inventory_store.add_movement.call_args[0][0]
        assert mvmt.unit_cost == 12.5
