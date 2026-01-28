"""Tests for SQLite sales store."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import aiosqlite
import pytest

from src.core.entities.local_sale import LocalSalesInvoice, LocalSalesItem
from src.infrastructure.storage.sqlite.sales_store import SQLiteSalesStore


@pytest.fixture
async def sales_db(tmp_path: Path):
    """Create temp database with sales schema."""
    db_path = tmp_path / "test_sales.db"
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
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await conn.execute("INSERT INTO materials (id, name, normalized_name) VALUES ('MAT-001', 'Cable', 'cable')")

        # Inventory table (needed for FK)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id TEXT NOT NULL,
                quantity_on_hand REAL NOT NULL DEFAULT 0.0,
                avg_cost REAL NOT NULL DEFAULT 0.0,
                last_movement_date DATE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("INSERT INTO inventory_items (material_id, quantity_on_hand, avg_cost) VALUES ('MAT-001', 100, 10.0)")

        # Sales tables
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS local_sales_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                sale_date DATE NOT NULL,
                subtotal REAL NOT NULL DEFAULT 0.0,
                tax_amount REAL NOT NULL DEFAULT 0.0,
                total_amount REAL NOT NULL DEFAULT 0.0,
                total_cost REAL NOT NULL DEFAULT 0.0,
                total_profit REAL NOT NULL DEFAULT 0.0,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS local_sales_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sales_invoice_id INTEGER NOT NULL,
                inventory_item_id INTEGER NOT NULL,
                material_id TEXT NOT NULL,
                description TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_price REAL NOT NULL,
                cost_basis REAL NOT NULL DEFAULT 0.0,
                line_total REAL NOT NULL DEFAULT 0.0,
                profit REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sales_invoice_id) REFERENCES local_sales_invoices(id)
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_items_invoice ON local_sales_items(sales_invoice_id)")

        await conn.commit()
    yield db_path


class TestSQLiteSalesStore:
    """Tests for SQLiteSalesStore."""

    async def test_create_invoice(self, sales_db):
        """Test creating a sales invoice with items."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = sales_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteSalesStore()
                invoice = LocalSalesInvoice(
                    invoice_number="LS-001",
                    customer_name="Test Customer",
                    sale_date=date(2024, 6, 15),
                    tax_amount=5.0,
                    items=[
                        LocalSalesItem(
                            inventory_item_id=1,
                            material_id="MAT-001",
                            description="Cable 3x2.5mm",
                            quantity=10.0,
                            unit_price=15.0,
                            cost_basis=100.0,
                        ),
                    ],
                )
                created = await store.create_invoice(invoice)
                assert created.id is not None
                assert len(created.items) == 1
                assert created.items[0].id is not None
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_get_invoice(self, sales_db):
        """Test getting a sales invoice with items."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = sales_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteSalesStore()
                invoice = LocalSalesInvoice(
                    invoice_number="LS-002",
                    customer_name="Test",
                    sale_date=date(2024, 6, 15),
                    items=[
                        LocalSalesItem(
                            inventory_item_id=1,
                            material_id="MAT-001",
                            description="Cable",
                            quantity=5.0,
                            unit_price=20.0,
                            cost_basis=50.0,
                        ),
                    ],
                )
                created = await store.create_invoice(invoice)
                fetched = await store.get_invoice(created.id)
                assert fetched is not None
                assert fetched.invoice_number == "LS-002"
                assert len(fetched.items) == 1
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_get_invoice_not_found(self, sales_db):
        """Test getting a non-existent invoice."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = sales_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteSalesStore()
                fetched = await store.get_invoice(9999)
                assert fetched is None
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_list_invoices(self, sales_db):
        """Test listing invoices."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = sales_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteSalesStore()
                for i in range(3):
                    await store.create_invoice(LocalSalesInvoice(
                        invoice_number=f"LS-{i:03d}",
                        customer_name="Test",
                        sale_date=date(2024, 6, 15),
                        items=[
                            LocalSalesItem(
                                inventory_item_id=1,
                                material_id="MAT-001",
                                description="Item",
                                quantity=1.0,
                                unit_price=10.0,
                            ),
                        ],
                    ))
                invoices = await store.list_invoices()
                assert len(invoices) == 3
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_list_invoices_pagination(self, sales_db):
        """Test pagination."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = sales_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteSalesStore()
                for i in range(5):
                    await store.create_invoice(LocalSalesInvoice(
                        invoice_number=f"LS-{i:03d}",
                        customer_name="Test",
                        sale_date=date(2024, 6, 15),
                        items=[
                            LocalSalesItem(
                                inventory_item_id=1,
                                material_id="MAT-001",
                                description="Item",
                                quantity=1.0,
                                unit_price=10.0,
                            ),
                        ],
                    ))
                page1 = await store.list_invoices(limit=2, offset=0)
                assert len(page1) == 2
                page2 = await store.list_invoices(limit=2, offset=2)
                assert len(page2) == 2
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()

    async def test_invoice_items_loaded(self, sales_db):
        """Test that items are properly loaded with invoice."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings = MagicMock()
        mock_settings.storage.db_path = sales_db
        mock_settings.storage.pool_size = 1
        mock_settings.storage.busy_timeout = 5000

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            try:
                store = SQLiteSalesStore()
                invoice = LocalSalesInvoice(
                    invoice_number="LS-010",
                    customer_name="Test",
                    sale_date=date(2024, 6, 15),
                    items=[
                        LocalSalesItem(
                            inventory_item_id=1,
                            material_id="MAT-001",
                            description="Item A",
                            quantity=2.0,
                            unit_price=10.0,
                            cost_basis=12.0,
                        ),
                        LocalSalesItem(
                            inventory_item_id=1,
                            material_id="MAT-001",
                            description="Item B",
                            quantity=3.0,
                            unit_price=20.0,
                            cost_basis=30.0,
                        ),
                    ],
                )
                created = await store.create_invoice(invoice)
                fetched = await store.get_invoice(created.id)
                assert fetched is not None
                assert len(fetched.items) == 2
                descs = [item.description for item in fetched.items]
                assert "Item A" in descs
                assert "Item B" in descs
            finally:
                from src.infrastructure.storage.sqlite.connection import close_pool

                await close_pool()
