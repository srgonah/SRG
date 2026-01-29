"""Abstract interface for inventory storage."""

from abc import ABC, abstractmethod

from src.core.entities.inventory import InventoryItem, StockMovement


class IInventoryStore(ABC):
    """Interface for inventory item and stock movement persistence."""

    @abstractmethod
    async def create_item(self, item: InventoryItem) -> InventoryItem:
        """Create a new inventory item."""
        pass

    @abstractmethod
    async def get_item(self, item_id: int) -> InventoryItem | None:
        """Get inventory item by ID."""
        pass

    @abstractmethod
    async def get_item_by_material(self, material_id: str) -> InventoryItem | None:
        """Get inventory item by material ID."""
        pass

    @abstractmethod
    async def update_item(self, item: InventoryItem) -> InventoryItem:
        """Update inventory item (quantity, avg_cost, etc.)."""
        pass

    @abstractmethod
    async def list_items(
        self, limit: int = 100, offset: int = 0
    ) -> list[InventoryItem]:
        """List inventory items with pagination."""
        pass

    @abstractmethod
    async def list_low_stock(
        self, threshold: float = 10.0, limit: int = 100, offset: int = 0
    ) -> list[InventoryItem]:
        """List inventory items where quantity_on_hand is at or below the threshold."""
        pass

    @abstractmethod
    async def add_movement(self, movement: StockMovement) -> StockMovement:
        """Record a stock movement."""
        pass

    @abstractmethod
    async def get_movements(
        self, inventory_item_id: int, limit: int = 100, offset: int = 0
    ) -> list[StockMovement]:
        """Get movements for an inventory item, ordered by date DESC."""
        pass
