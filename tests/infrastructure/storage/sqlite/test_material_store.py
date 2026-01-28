"""Tests for SQLiteMaterialStore."""

from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest

from src.core.entities.material import Material
from src.infrastructure.storage.sqlite.material_store import SQLiteMaterialStore


@pytest.fixture
async def material_db(tmp_path: Path):
    """Create a temporary database with materials schema (TEXT PKs)."""
    db_path = tmp_path / "test_materials.db"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = aiosqlite.Row

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
                name,
                description,
                content='materials',
                content_rowid='rowid'
            )
        """)

        # FTS sync triggers (using rowid for TEXT PK tables)
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

        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_materials_fts_delete
            AFTER DELETE ON materials
            BEGIN
                INSERT INTO materials_fts(materials_fts, rowid, name, description)
                VALUES ('delete', OLD.rowid, OLD.name, COALESCE(OLD.description, ''));
            END
        """)

        await conn.commit()

    return db_path


@pytest.fixture
def mock_pool(material_db):
    """Mock the connection pool to use our test database."""
    from src.infrastructure.storage.sqlite.connection import ConnectionPool

    pool = ConnectionPool(db_path=material_db, pool_size=2)

    async def get_test_pool():
        if not pool._initialized:
            await pool.initialize()
        return pool

    return pool, get_test_pool


@pytest.fixture
async def store(mock_pool):
    """Create a material store with mocked pool."""
    pool, get_test_pool = mock_pool
    await pool.initialize()

    with patch(
        "src.infrastructure.storage.sqlite.material_store.get_connection",
        side_effect=lambda: pool.acquire(),
    ), patch(
        "src.infrastructure.storage.sqlite.material_store.get_transaction",
        side_effect=lambda: pool.transaction(),
    ):
        s = SQLiteMaterialStore()
        yield s

    await pool.close()


@pytest.mark.asyncio
class TestSQLiteMaterialStore:
    """Tests for SQLiteMaterialStore CRUD."""

    async def test_create_material(self, store):
        """Create a material and verify it has a UUID string ID."""
        m = Material(name="PVC Cable 10mm", hs_code="8544.42", unit="M")
        result = await store.create_material(m)
        assert result.id is not None
        assert isinstance(result.id, str)
        assert len(result.id) == 36  # UUID format
        assert result.name == "PVC Cable 10mm"
        assert result.normalized_name == "pvc cable 10mm"

    async def test_get_material(self, store):
        """Get a material by ID."""
        m = Material(name="Steel Rod", hs_code="7214.10")
        created = await store.create_material(m)

        fetched = await store.get_material(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "Steel Rod"
        assert fetched.hs_code == "7214.10"

    async def test_get_material_not_found(self, store):
        """Get non-existent material returns None."""
        result = await store.get_material("nonexistent-uuid")
        assert result is None

    async def test_list_materials(self, store):
        """List materials with pagination."""
        await store.create_material(Material(name="Alpha"))
        await store.create_material(Material(name="Beta"))
        await store.create_material(Material(name="Gamma"))

        results = await store.list_materials(limit=2)
        assert len(results) == 2

        all_results = await store.list_materials(limit=10)
        assert len(all_results) == 3

    async def test_list_materials_by_category(self, store):
        """List materials filtered by category."""
        await store.create_material(Material(name="A", category="metal"))
        await store.create_material(Material(name="B", category="plastic"))
        await store.create_material(Material(name="C", category="metal"))

        metals = await store.list_materials(category="metal")
        assert len(metals) == 2

    async def test_search_by_name(self, store):
        """Search materials by name using FTS."""
        await store.create_material(
            Material(name="PVC Cable 10mm", description="Polyvinyl cable")
        )
        await store.create_material(Material(name="Steel Rod"))

        results = await store.search_by_name("PVC")
        assert len(results) >= 1
        assert results[0].name == "PVC Cable 10mm"

    async def test_find_by_normalized_name(self, store):
        """Find material by normalized name."""
        await store.create_material(Material(name="Widget A"))

        found = await store.find_by_normalized_name("widget a")
        assert found is not None
        assert found.name == "Widget A"

    async def test_find_by_normalized_name_not_found(self, store):
        """find_by_normalized_name returns None for unknown."""
        result = await store.find_by_normalized_name("nonexistent")
        assert result is None

    async def test_add_synonym(self, store):
        """Add a synonym to a material."""
        m = await store.create_material(Material(name="Widget A"))

        syn = await store.add_synonym(m.id, "widgeta")
        assert syn.id is not None
        assert isinstance(syn.id, str)
        assert syn.synonym == "widgeta"
        assert syn.material_id == m.id

    async def test_find_by_synonym(self, store):
        """Find material by synonym."""
        m = await store.create_material(Material(name="Widget A"))
        await store.add_synonym(m.id, "widgeta")

        found = await store.find_by_synonym("widgeta")
        assert found is not None
        assert found.id == m.id
        assert "widgeta" in found.synonyms

    async def test_find_by_synonym_case_insensitive(self, store):
        """find_by_synonym is case-insensitive."""
        m = await store.create_material(Material(name="Widget A"))
        await store.add_synonym(m.id, "WidgetA")

        found = await store.find_by_synonym("widgeta")
        assert found is not None
        assert found.id == m.id

    async def test_remove_synonym(self, store):
        """Remove a synonym."""
        m = await store.create_material(Material(name="Widget A"))
        syn = await store.add_synonym(m.id, "widgeta")

        removed = await store.remove_synonym(syn.id)
        assert removed is True

        # Verify synonym is gone
        found = await store.find_by_synonym("widgeta")
        assert found is None

    async def test_remove_synonym_not_found(self, store):
        """Remove non-existent synonym returns False."""
        result = await store.remove_synonym("nonexistent-uuid")
        assert result is False

    async def test_update_material(self, store):
        """Update material fields."""
        m = await store.create_material(Material(name="Widget A"))

        m.hs_code = "8471.30"
        m.category = "electronics"
        updated = await store.update_material(m)
        assert updated.hs_code == "8471.30"
        assert updated.category == "electronics"

        # Verify in DB
        fetched = await store.get_material(m.id)
        assert fetched is not None
        assert fetched.hs_code == "8471.30"

    async def test_create_with_explicit_id(self, store):
        """Create a material with a pre-set ID."""
        m = Material(name="Custom ID Mat", id="custom-id-abc")
        result = await store.create_material(m)
        assert result.id == "custom-id-abc"

        fetched = await store.get_material("custom-id-abc")
        assert fetched is not None
        assert fetched.name == "Custom ID Mat"

    async def test_multiple_synonyms(self, store):
        """Material can have multiple synonyms."""
        m = await store.create_material(Material(name="Copper Wire"))
        await store.add_synonym(m.id, "cu wire")
        await store.add_synonym(m.id, "copper cable")

        found = await store.find_by_synonym("cu wire")
        assert found is not None
        assert found.id == m.id
        assert len(found.synonyms) == 2

        found2 = await store.find_by_synonym("copper cable")
        assert found2 is not None
        assert found2.id == m.id
