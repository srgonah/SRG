"""Integration test for the catalog flow.

Tests the full flow: create invoice → add to catalog → query catalog.
"""

from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest

from src.application.dto.requests import AddToCatalogRequest
from src.application.use_cases.add_to_catalog import AddToCatalogUseCase
from src.core.entities.invoice import Invoice, LineItem, ParsingStatus, RowType
from src.infrastructure.storage.sqlite.invoice_store import SQLiteInvoiceStore
from src.infrastructure.storage.sqlite.material_store import SQLiteMaterialStore
from src.infrastructure.storage.sqlite.price_history_store import SQLitePriceHistoryStore


@pytest.fixture
async def full_db(tmp_path: Path):
    """Create a database with all schemas (v001+v002+v003)."""
    db_path = tmp_path / "test_full.db"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = aiosqlite.Row

        # Documents (needed for FK)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_filename TEXT,
                file_path TEXT,
                file_hash TEXT,
                file_size INTEGER DEFAULT 0,
                mime_type TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                version INTEGER DEFAULT 1,
                is_latest INTEGER DEFAULT 1,
                previous_version_id INTEGER,
                page_count INTEGER DEFAULT 0,
                company_key TEXT,
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                indexed_at TEXT
            )
        """)

        # Invoices
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
                invoice_no TEXT,
                invoice_date TEXT,
                seller_name TEXT,
                buyer_name TEXT,
                company_key TEXT,
                currency TEXT DEFAULT 'USD',
                total_amount REAL DEFAULT 0,
                subtotal REAL DEFAULT 0,
                tax_amount REAL DEFAULT 0,
                discount_amount REAL DEFAULT 0,
                total_quantity REAL DEFAULT 0,
                quality_score REAL DEFAULT 0,
                confidence REAL DEFAULT 0,
                template_confidence REAL DEFAULT 0,
                parser_version TEXT,
                template_id TEXT,
                parsing_status TEXT DEFAULT 'pending',
                error_message TEXT,
                bank_details_json TEXT,
                is_latest INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Invoice items
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                line_number INTEGER,
                item_name TEXT NOT NULL,
                description TEXT,
                hs_code TEXT,
                unit TEXT,
                brand TEXT,
                model TEXT,
                quantity REAL DEFAULT 0,
                unit_price REAL DEFAULT 0,
                total_price REAL DEFAULT 0,
                matched_material_id TEXT,
                row_type TEXT DEFAULT 'line_item'
            )
        """)

        # Invoice items FTS
        await conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS invoice_items_fts USING fts5(
                item_name,
                description,
                hs_code,
                content='invoice_items',
                content_rowid='id'
            )
        """)

        # Price history (v002)
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
                material_id TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Price history trigger
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_item_price_history
            AFTER INSERT ON invoice_items
            FOR EACH ROW
            WHEN NEW.row_type = 'line_item' AND NEW.unit_price > 0
            BEGIN
                INSERT INTO item_price_history (
                    item_name_normalized, hs_code, seller_name, invoice_id,
                    invoice_date, quantity, unit_price, currency
                )
                SELECT
                    LOWER(TRIM(NEW.item_name)), NEW.hs_code, inv.seller_name,
                    NEW.invoice_id, COALESCE(inv.invoice_date, date('now')),
                    NEW.quantity, NEW.unit_price, inv.currency
                FROM invoices inv WHERE inv.id = NEW.invoice_id;
            END
        """)

        # Stats view
        await conn.execute("""
            CREATE VIEW IF NOT EXISTS v_item_price_stats AS
            SELECT
                item_name_normalized, hs_code, seller_name, currency,
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

        # Materials (v005 - TEXT PKs + v007 ingestion columns)
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

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS material_synonyms (
                id TEXT PRIMARY KEY,
                material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                synonym TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'en',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        await conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS materials_fts USING fts5(
                name, description,
                content='materials', content_rowid='rowid'
            )
        """)

        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_materials_fts_insert
            AFTER INSERT ON materials
            BEGIN
                INSERT INTO materials_fts(rowid, name, description)
                VALUES (NEW.rowid, NEW.name, COALESCE(NEW.description, ''));
            END
        """)

        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_materials_fts_update
            AFTER UPDATE ON materials
            BEGIN
                INSERT INTO materials_fts(materials_fts, rowid, name, description)
                VALUES ('delete', OLD.rowid, OLD.name, COALESCE(OLD.description, ''));
                INSERT INTO materials_fts(rowid, name, description)
                VALUES (NEW.rowid, NEW.name, COALESCE(NEW.description, ''));
            END
        """)

        await conn.commit()

    return db_path


@pytest.fixture
async def stores(full_db):
    """Create stores connected to the full test database."""
    from src.infrastructure.storage.sqlite.connection import ConnectionPool

    pool = ConnectionPool(db_path=full_db, pool_size=2)
    await pool.initialize()

    patches = [
        patch(
            "src.infrastructure.storage.sqlite.invoice_store.get_connection",
            side_effect=lambda: pool.acquire(),
        ),
        patch(
            "src.infrastructure.storage.sqlite.invoice_store.get_transaction",
            side_effect=lambda: pool.transaction(),
        ),
        patch(
            "src.infrastructure.storage.sqlite.material_store.get_connection",
            side_effect=lambda: pool.acquire(),
        ),
        patch(
            "src.infrastructure.storage.sqlite.material_store.get_transaction",
            side_effect=lambda: pool.transaction(),
        ),
        patch(
            "src.infrastructure.storage.sqlite.price_history_store.get_connection",
            side_effect=lambda: pool.acquire(),
        ),
        patch(
            "src.infrastructure.storage.sqlite.price_history_store.get_transaction",
            side_effect=lambda: pool.transaction(),
        ),
    ]

    for p in patches:
        p.start()

    inv_store = SQLiteInvoiceStore()
    mat_store = SQLiteMaterialStore()
    price_store = SQLitePriceHistoryStore()

    yield inv_store, mat_store, price_store

    for p in patches:
        p.stop()

    await pool.close()


@pytest.mark.asyncio
class TestCatalogFlow:
    """Integration tests for the catalog flow."""

    async def test_full_catalog_flow(self, stores):
        """Full flow: create invoice → add to catalog → verify materials."""
        inv_store, mat_store, price_store = stores

        # 1. Create an invoice with items
        invoice = Invoice(
            invoice_no="INV-TEST-001",
            invoice_date="2024-01-15",
            seller_name="Test Corp",
            currency="USD",
            total_amount=650.0,
            parsing_status=ParsingStatus.OK,
            items=[
                LineItem(
                    line_number=1,
                    item_name="PVC Cable 10mm",
                    hs_code="8544.42",
                    unit="M",
                    quantity=100,
                    unit_price=5.0,
                    total_price=500.0,
                    row_type=RowType.LINE_ITEM,
                ),
                LineItem(
                    line_number=2,
                    item_name="Steel Rod 12mm",
                    hs_code="7214.10",
                    unit="KG",
                    quantity=50,
                    unit_price=3.0,
                    total_price=150.0,
                    row_type=RowType.LINE_ITEM,
                ),
            ],
        )
        created_invoice = await inv_store.create_invoice(invoice)
        assert created_invoice.id is not None

        # 2. Add to catalog
        use_case = AddToCatalogUseCase(
            invoice_store=inv_store,
            material_store=mat_store,
            price_store=price_store,
        )
        request = AddToCatalogRequest(invoice_id=created_invoice.id)
        result = await use_case.execute(request)

        assert result.materials_created == 2
        assert result.materials_updated == 0

        # 3. Verify materials exist in catalog
        materials = await mat_store.list_materials()
        assert len(materials) == 2

        # 4. Verify find by normalized name
        pvc = await mat_store.find_by_normalized_name("pvc cable 10mm")
        assert pvc is not None
        assert pvc.hs_code == "8544.42"

        # 5. Verify invoice items have matched_material_id set
        reloaded = await inv_store.get_invoice(created_invoice.id)
        assert reloaded is not None
        line_items = [i for i in reloaded.items if i.row_type == RowType.LINE_ITEM]
        for item in line_items:
            assert item.matched_material_id is not None, (
                f"Item '{item.item_name}' should have matched_material_id set"
            )

        # 6. Verify price history was linked
        history = await price_store.get_price_history(item_name="pvc cable")
        assert len(history) >= 1

        # 7. Verify price stats
        stats = await price_store.get_price_stats(item_name="pvc cable")
        assert len(stats) >= 1

    async def test_catalog_deduplication(self, stores):
        """Adding the same items twice doesn't create duplicates."""
        inv_store, mat_store, price_store = stores

        invoice = Invoice(
            invoice_no="INV-DUP-001",
            invoice_date="2024-02-01",
            seller_name="Test Corp",
            currency="USD",
            total_amount=500.0,
            parsing_status=ParsingStatus.OK,
            items=[
                LineItem(
                    line_number=1,
                    item_name="Widget X",
                    unit="PCS",
                    quantity=10,
                    unit_price=50.0,
                    total_price=500.0,
                    row_type=RowType.LINE_ITEM,
                ),
            ],
        )
        created = await inv_store.create_invoice(invoice)

        use_case = AddToCatalogUseCase(
            invoice_store=inv_store,
            material_store=mat_store,
            price_store=price_store,
        )

        # First add
        request = AddToCatalogRequest(invoice_id=created.id)
        result1 = await use_case.execute(request)
        assert result1.materials_created == 1

        # Second add - should update, not create
        result2 = await use_case.execute(request)
        assert result2.materials_created == 0
        assert result2.materials_updated == 1

        # Only one material should exist
        materials = await mat_store.list_materials()
        assert len(materials) == 1

    async def test_view_unmatched_add_to_catalog_verify_matched(self, stores):
        """Full workflow: upload -> view unmatched -> add-to-catalog -> verify matched ids."""
        inv_store, mat_store, price_store = stores

        # 1. Create invoice with unmatched items
        invoice = Invoice(
            invoice_no="INV-UNMATCHED-001",
            invoice_date="2024-03-01",
            seller_name="Unmatched Vendor",
            currency="AED",
            total_amount=1000.0,
            parsing_status=ParsingStatus.OK,
            items=[
                LineItem(
                    line_number=1,
                    item_name="Copper Wire 4mm",
                    hs_code="7408.11",
                    unit="M",
                    quantity=100,
                    unit_price=8.0,
                    total_price=800.0,
                    row_type=RowType.LINE_ITEM,
                    matched_material_id=None,  # Unmatched
                ),
                LineItem(
                    line_number=2,
                    item_name="Safety Helmet",
                    unit="PCS",
                    quantity=10,
                    unit_price=20.0,
                    total_price=200.0,
                    row_type=RowType.LINE_ITEM,
                    matched_material_id=None,  # Unmatched
                ),
            ],
        )
        created = await inv_store.create_invoice(invoice)
        assert created.id is not None

        # 2. Verify items are unmatched (simulating GET /api/invoices/{id}/items/unmatched)
        reloaded = await inv_store.get_invoice(created.id)
        unmatched_items = [
            item for item in reloaded.items
            if item.row_type == RowType.LINE_ITEM and not item.matched_material_id
        ]
        assert len(unmatched_items) == 2

        # 3. Add items to catalog
        use_case = AddToCatalogUseCase(
            invoice_store=inv_store,
            material_store=mat_store,
            price_store=price_store,
        )
        request = AddToCatalogRequest(invoice_id=created.id)
        result = await use_case.execute(request)

        assert result.materials_created == 2
        assert len(result.materials) == 2

        # 4. Verify items now have matched_material_id set
        final_invoice = await inv_store.get_invoice(created.id)
        line_items = [
            item for item in final_invoice.items
            if item.row_type == RowType.LINE_ITEM
        ]

        for item in line_items:
            assert item.matched_material_id is not None, (
                f"Item '{item.item_name}' should have matched_material_id after add-to-catalog"
            )

        # 5. Verify materials exist in catalog with correct data
        copper = await mat_store.find_by_normalized_name("copper wire 4mm")
        assert copper is not None
        assert copper.hs_code == "7408.11"
        assert copper.unit == "M"

        helmet = await mat_store.find_by_normalized_name("safety helmet")
        assert helmet is not None
        assert helmet.unit == "PCS"

    async def test_fts_search_returns_suggestions(self, stores):
        """Test that FTS5 search returns relevant suggestions for unmatched items."""
        inv_store, mat_store, price_store = stores

        # 1. First, create some materials in the catalog
        from src.core.entities.material import Material

        cable1 = Material(
            name="PVC Cable 2.5mm",
            normalized_name="pvc cable 2.5mm",
            hs_code="8544.49",
            unit="M",
            category="Electrical",
        )
        cable2 = Material(
            name="PVC Cable 4mm",
            normalized_name="pvc cable 4mm",
            hs_code="8544.49",
            unit="M",
            category="Electrical",
        )
        gloves = Material(
            name="Safety Gloves Leather",
            normalized_name="safety gloves leather",
            unit="PAIR",
            category="PPE",
        )

        await mat_store.create_material(cable1)
        await mat_store.create_material(cable2)
        await mat_store.create_material(gloves)

        # 2. Search using FTS5 (simulating the unmatched items suggestions)
        results = await mat_store.search_by_name("PVC Cable", limit=5)

        assert len(results) >= 2
        # Results should include both PVC cables
        names = [r.name for r in results]
        assert any("PVC Cable 2.5mm" in n for n in names)
        assert any("PVC Cable 4mm" in n for n in names)

        # 3. Search for gloves
        glove_results = await mat_store.search_by_name("safety gloves", limit=5)
        assert len(glove_results) >= 1
        assert any("Safety Gloves" in r.name for r in glove_results)

    async def test_auto_match_links_existing_materials(self, stores):
        """Test auto_match_items links items to existing materials."""
        inv_store, mat_store, price_store = stores

        # 1. Pre-create a material in catalog
        from src.core.entities.material import Material

        existing_material = Material(
            name="Industrial Motor 5HP",
            normalized_name="industrial motor 5hp",
            hs_code="8501.52",
            unit="PCS",
        )
        await mat_store.create_material(existing_material)

        # 2. Create invoice with item matching existing material
        invoice = Invoice(
            invoice_no="INV-AUTOMATCH-001",
            invoice_date="2024-04-01",
            seller_name="Motor Supplier",
            currency="USD",
            total_amount=500.0,
            parsing_status=ParsingStatus.OK,
            items=[
                LineItem(
                    line_number=1,
                    item_name="Industrial Motor 5HP",  # Exact match
                    unit="PCS",
                    quantity=2,
                    unit_price=250.0,
                    total_price=500.0,
                    row_type=RowType.LINE_ITEM,
                    matched_material_id=None,
                ),
            ],
        )
        created = await inv_store.create_invoice(invoice)

        # 3. Run auto-match
        use_case = AddToCatalogUseCase(
            invoice_store=inv_store,
            material_store=mat_store,
            price_store=price_store,
        )
        auto_result = await use_case.auto_match_items(created.id)

        # Should match existing material, not create new
        assert auto_result.matched == 1
        assert auto_result.unmatched == 0

        # 4. Verify item is linked to existing material
        final_invoice = await inv_store.get_invoice(created.id)
        line_items = [
            item for item in final_invoice.items
            if item.row_type == RowType.LINE_ITEM
        ]

        assert len(line_items) == 1
        assert line_items[0].matched_material_id == existing_material.id
