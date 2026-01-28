"""Tests for SQLite inventory store."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import aiosqlite
import pytest

from src.core.entities.inventory import InventoryItem, MovementType, StockMovement
from src.infrastructure.storage.sqlite.inventory_store import SQLiteInventoryStore


@pytest.fixture
async def inventory_db(tmp_path: Path):
    """Create temp database with inventory schema."""
    db_path = tmp_path / "test_inv.db"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = aiosqlite.Row

        # Materials table (needed for FK)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                hs_code TEXT,
                category TEXT,
                unit TEXT,
                description TEXT,
                source_url TEXT,
                origin_country TEXT,
                origin_confidence TEXT NOT NULL DEFAULT 'unknown',
                evidence_text TEXT,
                brand TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Insert test materials
        await conn.execute("""
            INSERT INTO materials (id, name, normalized_name)
            VALUES ('MAT-001', 'Cable 3x2.5mm', 'cable 3x2.5mm')
        """)
        await conn.execute("""
            INSERT INTO materials (id, name, normalized_name)
            VALUES ('MAT-002', 'PVC Pipe', 'pvc pipe')
        """)

        # Inventory tables
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id TEXT NOT NULL,
                quantity_on_hand REAL NOT NULL DEFAULT 0.0,
                avg_cost REAL NOT NULL DEFAULT 0.0,
                last_movement_date DATE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (material_id) REFERENCES materials(id)
            )
        """)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_material ON inventory_items(material_id)
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inventory_item_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL CHECK(movement_type IN ('in', 'out', 'adjust')),
                quantity REAL NOT NULL,
                unit_cost REAL NOT NULL DEFAULT 0.0,
                reference TEXT,
                notes TEXT,
                movement_date DATE NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_movements_item ON stock_movements(inventory_item_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_movements_date ON stock_movements(movement_date)")

        await conn.commit()
    yield db_path


class TestSQLiteInventoryStore:
    """Tests for SQLiteInventoryStore."""

    async def test_create_item(self, inventory_db):
        """Test creating an inventory item."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = inventory_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteInventoryStore()
                item = InventoryItem(material_id="MAT-001")
                created = await store.create_item(item)
                assert created.id is not None
                assert created.material_id == "MAT-001"
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_get_item(self, inventory_db):
        """Test getting an inventory item by ID."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = inventory_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteInventoryStore()
                item = InventoryItem(material_id="MAT-001")
                created = await store.create_item(item)
                fetched = await store.get_item(created.id)
                assert fetched is not None
                assert fetched.material_id == "MAT-001"
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_get_item_by_material(self, inventory_db):
        """Test getting an inventory item by material_id."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = inventory_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteInventoryStore()
                item = InventoryItem(material_id="MAT-002")
                await store.create_item(item)
                fetched = await store.get_item_by_material("MAT-002")
                assert fetched is not None
                assert fetched.material_id == "MAT-002"
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_get_item_not_found(self, inventory_db):
        """Test getting a non-existent item."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = inventory_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteInventoryStore()
                fetched = await store.get_item(9999)
                assert fetched is None
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_update_item(self, inventory_db):
        """Test updating an inventory item."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = inventory_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteInventoryStore()
                item = InventoryItem(material_id="MAT-001")
                created = await store.create_item(item)
                created.quantity_on_hand = 100.0
                created.avg_cost = 10.0
                created.last_movement_date = date(2024, 6, 15)
                updated = await store.update_item(created)
                assert updated.quantity_on_hand == 100.0
                assert updated.avg_cost == 10.0
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_list_items(self, inventory_db):
        """Test listing inventory items."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = inventory_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteInventoryStore()
                await store.create_item(InventoryItem(material_id="MAT-001"))
                await store.create_item(InventoryItem(material_id="MAT-002"))
                items = await store.list_items()
                assert len(items) == 2
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_add_movement(self, inventory_db):
        """Test adding a stock movement."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = inventory_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteInventoryStore()
                item = await store.create_item(InventoryItem(material_id="MAT-001"))
                mvmt = StockMovement(
                    inventory_item_id=item.id,
                    movement_type=MovementType.IN,
                    quantity=50.0,
                    unit_cost=10.0,
                    reference="PO-001",
                    movement_date=date(2024, 6, 15),
                )
                created = await store.add_movement(mvmt)
                assert created.id is not None
                assert created.movement_type == MovementType.IN
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_get_movements(self, inventory_db):
        """Test getting movements for an item."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = inventory_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteInventoryStore()
                item = await store.create_item(InventoryItem(material_id="MAT-001"))
                await store.add_movement(StockMovement(
                    inventory_item_id=item.id,
                    movement_type=MovementType.IN,
                    quantity=50.0,
                    unit_cost=10.0,
                    movement_date=date(2024, 6, 15),
                ))
                await store.add_movement(StockMovement(
                    inventory_item_id=item.id,
                    movement_type=MovementType.OUT,
                    quantity=20.0,
                    unit_cost=10.0,
                    movement_date=date(2024, 6, 16),
                ))
                movements = await store.get_movements(item.id)
                assert len(movements) == 2
                # Should be ordered by date DESC
                assert movements[0].movement_type == MovementType.OUT
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_get_item_by_material_not_found(self, inventory_db):
        """Test getting by non-existent material."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = inventory_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteInventoryStore()
                fetched = await store.get_item_by_material("NONEXISTENT")
                assert fetched is None
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_unique_material_constraint(self, inventory_db):
        """Test that material_id unique constraint is enforced."""
        import sqlite3

        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = inventory_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteInventoryStore()
                await store.create_item(InventoryItem(material_id="MAT-001"))
                with pytest.raises(sqlite3.IntegrityError):
                    await store.create_item(InventoryItem(material_id="MAT-001"))
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()
