-- Migration: v003_materials
-- Description: Add materials catalog with synonyms and FTS search
-- Version: 1.2.0
-- Created: 2026-01-27
-- Dependencies: v002_price_history

-- ============================================================
-- Materials Catalog Table
-- ============================================================

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    hs_code TEXT,
    category TEXT,
    unit TEXT,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_materials_normalized_name ON materials(normalized_name);
CREATE INDEX IF NOT EXISTS idx_materials_hs_code ON materials(hs_code);

-- ============================================================
-- Material Synonyms Table
-- ============================================================

CREATE TABLE IF NOT EXISTS material_synonyms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    synonym TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_material_synonyms_material ON material_synonyms(material_id);
CREATE INDEX IF NOT EXISTS idx_material_synonyms_synonym ON material_synonyms(synonym);

-- ============================================================
-- Materials FTS5 Virtual Table
-- ============================================================

CREATE VIRTUAL TABLE IF NOT EXISTS materials_fts USING fts5(
    name,
    description,
    content='materials',
    content_rowid='id'
);

-- ============================================================
-- FTS Sync Triggers
-- ============================================================

CREATE TRIGGER IF NOT EXISTS trg_materials_fts_insert
AFTER INSERT ON materials
BEGIN
    INSERT INTO materials_fts(rowid, name, description)
    VALUES (NEW.id, NEW.name, COALESCE(NEW.description, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_materials_fts_update
AFTER UPDATE ON materials
BEGIN
    INSERT INTO materials_fts(materials_fts, rowid, name, description)
    VALUES ('delete', OLD.id, OLD.name, COALESCE(OLD.description, ''));
    INSERT INTO materials_fts(rowid, name, description)
    VALUES (NEW.id, NEW.name, COALESCE(NEW.description, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_materials_fts_delete
AFTER DELETE ON materials
BEGIN
    INSERT INTO materials_fts(materials_fts, rowid, name, description)
    VALUES ('delete', OLD.id, OLD.name, COALESCE(OLD.description, ''));
END;

-- ============================================================
-- Link price history to materials
-- ============================================================

ALTER TABLE item_price_history ADD COLUMN material_id INTEGER REFERENCES materials(id);

CREATE INDEX IF NOT EXISTS idx_price_history_material ON item_price_history(material_id);

-- ============================================================
-- Record migration
-- ============================================================

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES ('003', 'materials');
