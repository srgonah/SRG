"""Tests for SQLitePriceHistoryStore."""

from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest

from src.infrastructure.storage.sqlite.price_history_store import SQLitePriceHistoryStore


@pytest.fixture
async def price_db(tmp_path: Path):
    """Create a temporary database with price history schema."""
    db_path = tmp_path / "test_prices.db"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = aiosqlite.Row

        # Minimal invoices table for FK
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_name TEXT,
                currency TEXT DEFAULT 'USD',
                invoice_date TEXT
            )
        """)

        # Price history table (v002 schema + v003 material_id)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS item_price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name_normalized TEXT NOT NULL,
                hs_code TEXT,
                seller_name TEXT,
                invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                invoice_date TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_price REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                material_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Stats view
        await conn.execute("""
            CREATE VIEW IF NOT EXISTS v_item_price_stats AS
            SELECT
                item_name_normalized,
                hs_code,
                seller_name,
                currency,
                COUNT(*) AS occurrence_count,
                MIN(unit_price) AS min_price,
                MAX(unit_price) AS max_price,
                AVG(unit_price) AS avg_price,
                CASE
                    WHEN MAX(unit_price) = MIN(unit_price) THEN 'stable'
                    WHEN (MAX(unit_price) - MIN(unit_price)) / AVG(unit_price) < 0.05 THEN 'stable'
                    WHEN (MAX(unit_price) - MIN(unit_price)) / AVG(unit_price) < 0.20 THEN 'moderate'
                    ELSE 'volatile'
                END AS price_trend,
                MIN(invoice_date) AS first_seen,
                MAX(invoice_date) AS last_seen
            FROM item_price_history
            GROUP BY item_name_normalized, hs_code, seller_name, currency
        """)

        # Insert test data
        await conn.execute(
            "INSERT INTO invoices (id, seller_name, currency, invoice_date) VALUES (1, 'ACME', 'USD', '2024-01-15')"
        )
        await conn.execute(
            "INSERT INTO invoices (id, seller_name, currency, invoice_date) VALUES (2, 'ACME', 'USD', '2024-06-15')"
        )
        await conn.execute("""
            INSERT INTO item_price_history (item_name_normalized, hs_code, seller_name, invoice_id, invoice_date, quantity, unit_price, currency)
            VALUES ('pvc cable 10mm', '8544.42', 'ACME', 1, '2024-01-15', 100, 5.00, 'USD')
        """)
        await conn.execute("""
            INSERT INTO item_price_history (item_name_normalized, hs_code, seller_name, invoice_id, invoice_date, quantity, unit_price, currency)
            VALUES ('pvc cable 10mm', '8544.42', 'ACME', 2, '2024-06-15', 200, 5.50, 'USD')
        """)
        await conn.execute("""
            INSERT INTO item_price_history (item_name_normalized, hs_code, seller_name, invoice_id, invoice_date, quantity, unit_price, currency)
            VALUES ('steel rod', '7214.10', 'BetaCo', 1, '2024-01-15', 50, 3.00, 'USD')
        """)

        await conn.commit()

    return db_path


@pytest.fixture
def mock_pool(price_db):
    """Mock the connection pool to use our test database."""
    from src.infrastructure.storage.sqlite.connection import ConnectionPool

    pool = ConnectionPool(db_path=price_db, pool_size=2)
    return pool


@pytest.fixture
async def store(mock_pool):
    """Create a price history store with mocked pool."""
    pool = mock_pool
    await pool.initialize()

    with patch(
        "src.infrastructure.storage.sqlite.price_history_store.get_connection",
        side_effect=lambda: pool.acquire(),
    ), patch(
        "src.infrastructure.storage.sqlite.price_history_store.get_transaction",
        side_effect=lambda: pool.transaction(),
    ):
        s = SQLitePriceHistoryStore()
        yield s

    await pool.close()


@pytest.mark.asyncio
class TestSQLitePriceHistoryStore:
    """Tests for price history store."""

    async def test_get_price_history_all(self, store):
        """Get all price history entries."""
        entries = await store.get_price_history()
        assert len(entries) == 3

    async def test_get_price_history_filter_item(self, store):
        """Filter price history by item name."""
        entries = await store.get_price_history(item_name="pvc cable")
        assert len(entries) == 2
        assert all("pvc cable" in e["item_name"] for e in entries)

    async def test_get_price_history_filter_seller(self, store):
        """Filter price history by seller."""
        entries = await store.get_price_history(seller="BetaCo")
        assert len(entries) == 1
        assert entries[0]["seller_name"] == "BetaCo"

    async def test_get_price_history_date_range(self, store):
        """Filter price history by date range."""
        entries = await store.get_price_history(
            date_from="2024-03-01", date_to="2024-12-31"
        )
        assert len(entries) == 1
        assert entries[0]["invoice_date"] == "2024-06-15"

    async def test_get_price_history_limit(self, store):
        """Limit number of returned entries."""
        entries = await store.get_price_history(limit=1)
        assert len(entries) == 1

    async def test_get_price_stats(self, store):
        """Get price statistics."""
        stats = await store.get_price_stats()
        assert len(stats) == 2  # Two distinct item/seller combinations

    async def test_get_price_stats_filter_item(self, store):
        """Filter stats by item name."""
        stats = await store.get_price_stats(item_name="pvc cable")
        assert len(stats) == 1
        assert stats[0]["occurrence_count"] == 2
        assert stats[0]["min_price"] == 5.0
        assert stats[0]["max_price"] == 5.5

    async def test_get_price_stats_filter_seller(self, store):
        """Filter stats by seller."""
        stats = await store.get_price_stats(seller="BetaCo")
        assert len(stats) == 1
        assert stats[0]["item_name"] == "steel rod"

    async def test_link_material(self, store):
        """Link material to price history rows."""
        updated = await store.link_material(42, "pvc cable 10mm")
        assert updated == 2  # Two rows for pvc cable
