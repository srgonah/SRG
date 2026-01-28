"""Tests for ReceiveStockUseCase."""

from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest

from src.application.dto.requests import ReceiveStockRequest
from src.application.use_cases.receive_stock import ReceiveStockUseCase
from src.core.entities.inventory import InventoryItem, MovementType, StockMovement
from src.core.entities.material import Material
from src.core.exceptions import MaterialNotFoundError


@pytest.fixture
def mock_inventory_store():
    store = AsyncMock()
    return store


@pytest.fixture
def mock_material_store():
    store = AsyncMock()
    return store


@pytest.fixture
def use_case(mock_inventory_store, mock_material_store):
    return ReceiveStockUseCase(
        inventory_store=mock_inventory_store,
        material_store=mock_material_store,
    )


class TestReceiveStockUseCase:
    async def test_new_item_created(self, use_case, mock_inventory_store, mock_material_store):
        """Test receiving stock creates new inventory item when none exists."""
        mock_material_store.get_material.return_value = Material(
            id="MAT-001", name="Cable", normalized_name="cable",
        )
        mock_inventory_store.get_item_by_material.return_value = None
        new_item = InventoryItem(id=1, material_id="MAT-001")
        mock_inventory_store.create_item.return_value = new_item
        mock_inventory_store.update_item.return_value = new_item
        mock_inventory_store.add_movement.return_value = StockMovement(
            id=1, inventory_item_id=1, movement_type=MovementType.IN,
            quantity=100, unit_cost=10.0, movement_date=date.today(),
        )

        request = ReceiveStockRequest(material_id="MAT-001", quantity=100, unit_cost=10.0)
        result = await use_case.execute(request)
        assert result.created is True
        mock_inventory_store.create_item.assert_called_once()

    async def test_existing_item_wac_updated(self, use_case, mock_inventory_store, mock_material_store):
        """Test WAC recalculation on existing item."""
        mock_material_store.get_material.return_value = Material(
            id="MAT-001", name="Cable", normalized_name="cable",
        )
        existing = InventoryItem(
            id=1, material_id="MAT-001", quantity_on_hand=100.0, avg_cost=10.0,
        )
        mock_inventory_store.get_item_by_material.return_value = existing
        mock_inventory_store.update_item.return_value = existing
        mock_inventory_store.add_movement.return_value = StockMovement(
            id=1, inventory_item_id=1, movement_type=MovementType.IN,
            quantity=50, unit_cost=12.0, movement_date=date.today(),
        )

        request = ReceiveStockRequest(material_id="MAT-001", quantity=50, unit_cost=12.0)
        result = await use_case.execute(request)
        assert result.created is False
        # WAC = (100*10 + 50*12) / 150 = 10.667
        updated_item = mock_inventory_store.update_item.call_args[0][0]
        assert updated_item.quantity_on_hand == 150.0
        assert round(updated_item.avg_cost, 2) == 10.67

    async def test_material_not_found(self, use_case, mock_material_store):
        """Test error when material doesn't exist."""
        mock_material_store.get_material.return_value = None
        request = ReceiveStockRequest(material_id="NONEXISTENT", quantity=10, unit_cost=5.0)
        with pytest.raises(MaterialNotFoundError):
            await use_case.execute(request)

    async def test_movement_recorded(self, use_case, mock_inventory_store, mock_material_store):
        """Test that a stock movement is recorded."""
        mock_material_store.get_material.return_value = Material(
            id="MAT-001", name="Cable", normalized_name="cable",
        )
        mock_inventory_store.get_item_by_material.return_value = InventoryItem(
            id=1, material_id="MAT-001",
        )
        mock_inventory_store.update_item.return_value = InventoryItem(id=1, material_id="MAT-001")
        mock_inventory_store.add_movement.return_value = StockMovement(
            id=1, inventory_item_id=1, movement_type=MovementType.IN,
            quantity=10, unit_cost=5.0, movement_date=date.today(),
        )

        request = ReceiveStockRequest(
            material_id="MAT-001", quantity=10, unit_cost=5.0,
            reference="PO-001", notes="Test receipt",
        )
        await use_case.execute(request)
        mock_inventory_store.add_movement.assert_called_once()
        mvmt_arg = mock_inventory_store.add_movement.call_args[0][0]
        assert mvmt_arg.movement_type == MovementType.IN
        assert mvmt_arg.reference == "PO-001"

    async def test_to_response(self, use_case, mock_inventory_store, mock_material_store):
        """Test to_response conversion."""
        mock_material_store.get_material.return_value = Material(
            id="MAT-001", name="Cable", normalized_name="cable",
        )
        now = datetime.utcnow()
        item = InventoryItem(
            id=1, material_id="MAT-001", quantity_on_hand=100,
            avg_cost=10.0, created_at=now, updated_at=now,
        )
        mock_inventory_store.get_item_by_material.return_value = item
        mock_inventory_store.update_item.return_value = item
        mock_inventory_store.add_movement.return_value = StockMovement(
            id=1, inventory_item_id=1, movement_type=MovementType.IN,
            quantity=100, unit_cost=10.0, movement_date=date.today(),
            created_at=now,
        )

        request = ReceiveStockRequest(material_id="MAT-001", quantity=100, unit_cost=10.0)
        result = await use_case.execute(request)
        response = use_case.to_response(result)
        assert response.inventory_item.material_id == "MAT-001"
        assert response.movement.movement_type == "in"
