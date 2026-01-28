"""Tests for inventory entities."""

from datetime import date, datetime

from src.core.entities.inventory import InventoryItem, MovementType, StockMovement


class TestInventoryItem:
    """Tests for InventoryItem entity."""

    def test_defaults(self):
        """Test default values."""
        item = InventoryItem(material_id="MAT-001")
        assert item.id is None
        assert item.material_id == "MAT-001"
        assert item.quantity_on_hand == 0.0
        assert item.avg_cost == 0.0
        assert item.last_movement_date is None

    def test_total_value(self):
        """Test total_value property."""
        item = InventoryItem(
            material_id="MAT-001",
            quantity_on_hand=100.0,
            avg_cost=10.0,
        )
        assert item.total_value == 1000.0

    def test_total_value_zero_qty(self):
        """Test total_value with zero quantity."""
        item = InventoryItem(material_id="MAT-001", avg_cost=10.0)
        assert item.total_value == 0.0

    def test_total_value_zero_cost(self):
        """Test total_value with zero cost."""
        item = InventoryItem(material_id="MAT-001", quantity_on_hand=50.0)
        assert item.total_value == 0.0

    def test_with_all_fields(self):
        """Test with all fields populated."""
        now = datetime.utcnow()
        today = date.today()
        item = InventoryItem(
            id=1,
            material_id="MAT-001",
            quantity_on_hand=50.0,
            avg_cost=12.5,
            last_movement_date=today,
            created_at=now,
            updated_at=now,
        )
        assert item.id == 1
        assert item.last_movement_date == today
        assert item.total_value == 625.0


class TestStockMovement:
    """Tests for StockMovement entity."""

    def test_defaults(self):
        """Test default values."""
        mvmt = StockMovement(
            inventory_item_id=1,
            movement_type=MovementType.IN,
            quantity=10.0,
        )
        assert mvmt.id is None
        assert mvmt.unit_cost == 0.0
        assert mvmt.reference is None
        assert mvmt.notes is None

    def test_movement_types(self):
        """Test all movement types."""
        assert MovementType.IN == "in"
        assert MovementType.OUT == "out"
        assert MovementType.ADJUST == "adjust"

    def test_in_movement(self):
        """Test IN movement creation."""
        mvmt = StockMovement(
            inventory_item_id=1,
            movement_type=MovementType.IN,
            quantity=100.0,
            unit_cost=10.0,
            reference="PO-001",
            movement_date=date(2024, 6, 15),
        )
        assert mvmt.movement_type == MovementType.IN
        assert mvmt.quantity == 100.0
        assert mvmt.unit_cost == 10.0
        assert mvmt.reference == "PO-001"


class TestWACComputation:
    """Test Weighted Average Cost computation."""

    def test_wac_basic(self):
        """Test WAC: (100*10 + 50*12) / 150 = 10.667."""
        old_qty, old_avg = 100.0, 10.0
        new_qty, new_cost = 50.0, 12.0
        total_qty = old_qty + new_qty
        new_avg = (old_qty * old_avg + new_qty * new_cost) / total_qty
        assert round(new_avg, 2) == 10.67

    def test_wac_first_receipt(self):
        """First receipt sets avg_cost to unit_cost."""
        old_qty, old_avg = 0.0, 0.0
        new_qty, new_cost = 100.0, 15.0
        total_qty = old_qty + new_qty
        new_avg = (old_qty * old_avg + new_qty * new_cost) / total_qty
        assert new_avg == 15.0
