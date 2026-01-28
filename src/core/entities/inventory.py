"""Inventory domain entities."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


class MovementType(str, Enum):
    """Types of stock movements."""

    IN = "in"
    OUT = "out"
    ADJUST = "adjust"


class InventoryItem(BaseModel):
    """Tracks stock level and weighted average cost for a material."""

    id: int | None = None
    material_id: str  # FK → materials.id
    quantity_on_hand: float = 0.0
    avg_cost: float = 0.0  # Weighted Average Cost
    last_movement_date: date | None = None
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

    @property
    def total_value(self) -> float:
        """Total inventory value = quantity * avg_cost."""
        return self.quantity_on_hand * self.avg_cost


class StockMovement(BaseModel):
    """Records a single stock movement (in, out, or adjustment)."""

    id: int | None = None
    inventory_item_id: int  # FK → inventory_items.id
    movement_type: MovementType
    quantity: float  # always positive
    unit_cost: float = 0.0
    reference: str | None = None  # e.g., invoice number, PO number
    notes: str | None = None
    movement_date: date = date.today()
    created_at: datetime = datetime.utcnow()
