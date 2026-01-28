"""SQLite implementation of inventory storage."""

from datetime import date, datetime

import aiosqlite

from src.config import get_logger
from src.core.entities.inventory import InventoryItem, MovementType, StockMovement
from src.core.interfaces.inventory_store import IInventoryStore
from src.infrastructure.storage.sqlite.connection import get_connection, get_transaction

logger = get_logger(__name__)


class SQLiteInventoryStore(IInventoryStore):
    """SQLite implementation of inventory item and stock movement storage."""

    async def create_item(self, item: InventoryItem) -> InventoryItem:
        """Create a new inventory item."""
        now = datetime.utcnow()
        item.created_at = now
        item.updated_at = now
        async with get_transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO inventory_items (
                    material_id, quantity_on_hand, avg_cost,
                    last_movement_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.material_id,
                    item.quantity_on_hand,
                    item.avg_cost,
                    item.last_movement_date.isoformat() if item.last_movement_date else None,
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                ),
            )
            item.id = cursor.lastrowid
            logger.info(
                "inventory_item_created",
                item_id=item.id,
                material_id=item.material_id,
            )
            return item

    async def get_item(self, item_id: int) -> InventoryItem | None:
        """Get inventory item by ID."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM inventory_items WHERE id = ?", (item_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_inventory_item(row)

    async def get_item_by_material(self, material_id: str) -> InventoryItem | None:
        """Get inventory item by material ID."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM inventory_items WHERE material_id = ?",
                (material_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_inventory_item(row)

    async def update_item(self, item: InventoryItem) -> InventoryItem:
        """Update inventory item."""
        item.updated_at = datetime.utcnow()
        async with get_transaction() as conn:
            await conn.execute(
                """
                UPDATE inventory_items SET
                    quantity_on_hand = ?,
                    avg_cost = ?,
                    last_movement_date = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    item.quantity_on_hand,
                    item.avg_cost,
                    item.last_movement_date.isoformat() if item.last_movement_date else None,
                    item.updated_at.isoformat(),
                    item.id,
                ),
            )
            logger.info("inventory_item_updated", item_id=item.id)
            return item

    async def list_items(
        self, limit: int = 100, offset: int = 0
    ) -> list[InventoryItem]:
        """List inventory items with pagination."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM inventory_items
                ORDER BY material_id
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = await cursor.fetchall()
            return [self._row_to_inventory_item(row) for row in rows]

    async def add_movement(self, movement: StockMovement) -> StockMovement:
        """Record a stock movement."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO stock_movements (
                    inventory_item_id, movement_type, quantity,
                    unit_cost, reference, notes, movement_date, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    movement.inventory_item_id,
                    movement.movement_type.value,
                    movement.quantity,
                    movement.unit_cost,
                    movement.reference,
                    movement.notes,
                    movement.movement_date.isoformat(),
                    movement.created_at.isoformat(),
                ),
            )
            movement.id = cursor.lastrowid
            logger.info(
                "stock_movement_recorded",
                movement_id=movement.id,
                type=movement.movement_type.value,
                qty=movement.quantity,
            )
            return movement

    async def get_movements(
        self, inventory_item_id: int, limit: int = 100
    ) -> list[StockMovement]:
        """Get movements for an inventory item, ordered by date DESC."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM stock_movements
                WHERE inventory_item_id = ?
                ORDER BY movement_date DESC, id DESC
                LIMIT ?
                """,
                (inventory_item_id, limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_movement(row) for row in rows]

    @staticmethod
    def _row_to_inventory_item(row: aiosqlite.Row) -> InventoryItem:
        """Convert a database row to an InventoryItem entity."""
        last_movement_date = None
        if row["last_movement_date"]:
            try:
                last_movement_date = date.fromisoformat(row["last_movement_date"])
            except (ValueError, TypeError):
                pass

        created_at = datetime.utcnow()
        if row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except (ValueError, TypeError):
                pass

        updated_at = datetime.utcnow()
        if row["updated_at"]:
            try:
                updated_at = datetime.fromisoformat(row["updated_at"])
            except (ValueError, TypeError):
                pass

        return InventoryItem(
            id=row["id"],
            material_id=row["material_id"],
            quantity_on_hand=float(row["quantity_on_hand"]),
            avg_cost=float(row["avg_cost"]),
            last_movement_date=last_movement_date,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _row_to_movement(row: aiosqlite.Row) -> StockMovement:
        """Convert a database row to a StockMovement entity."""
        movement_date = date.today()
        if row["movement_date"]:
            try:
                movement_date = date.fromisoformat(row["movement_date"])
            except (ValueError, TypeError):
                pass

        created_at = datetime.utcnow()
        if row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except (ValueError, TypeError):
                pass

        return StockMovement(
            id=row["id"],
            inventory_item_id=row["inventory_item_id"],
            movement_type=MovementType(row["movement_type"]),
            quantity=float(row["quantity"]),
            unit_cost=float(row["unit_cost"]),
            reference=row["reference"],
            notes=row["notes"],
            movement_date=movement_date,
            created_at=created_at,
        )
