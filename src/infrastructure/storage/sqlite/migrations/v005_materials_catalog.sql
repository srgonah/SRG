-- Migration: v005_materials_catalog
-- Description: Recreate materials catalog with TEXT primary keys and enhanced FTS
-- Version: 1.3.0
-- Created: 2026-01-27
-- Dependencies: v004_company_docs_reminders
-- Note: Replaces v003 INTEGER PK schema with TEXT PK schema.

-- ============================================================
-- Drop old v003 objects (triggers first, then FTS, then tables)
-- ============================================================

DROP TRIGGER IF EXISTS trg_materials_fts_insert;
DROP TRIGGER IF EXISTS trg_materials_fts_update;
DROP TRIGGER IF EXISTS trg_materials_fts_delete;
DROP TABLE IF EXISTS materials_fts;
DROP TABLE IF EXISTS material_synonyms;
DROP TABLE IF EXISTS materials;

-- ============================================================
-- Materials Catalog Table (TEXT PK)
-- ============================================================

CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    hs_code TEXT,
    category TEXT,
    unit TEXT,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_materials_normalized_name ON materials(normalized_name);
CREATE INDEX IF NOT EXISTS idx_materials_hs_code ON materials(hs_code);
CREATE INDEX IF NOT EXISTS idx_materials_category ON materials(category);

-- ============================================================
-- Material Synonyms Table (TEXT PK, TEXT FK)
-- ============================================================

CREATE TABLE IF NOT EXISTS material_synonyms (
    id TEXT PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    synonym TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
    content_rowid='rowid'
);

-- ============================================================
-- FTS Sync Triggers
-- ============================================================

CREATE TRIGGER IF NOT EXISTS trg_materials_fts_insert
AFTER INSERT ON materials
BEGIN
    INSERT INTO materials_fts(rowid, name, description)
    VALUES (NEW.rowid, NEW.name, COALESCE(NEW.description, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_materials_fts_update
AFTER UPDATE ON materials
BEGIN
    INSERT INTO materials_fts(materials_fts, rowid, name, description)
    VALUES ('delete', OLD.rowid, OLD.name, COALESCE(OLD.description, ''));
    INSERT INTO materials_fts(rowid, name, description)
    VALUES (NEW.rowid, NEW.name, COALESCE(NEW.description, ''));
END;

CREATE TRIGGER IF NOT EXISTS trg_materials_fts_delete
AFTER DELETE ON materials
BEGIN
    INSERT INTO materials_fts(materials_fts, rowid, name, description)
    VALUES ('delete', OLD.rowid, OLD.name, COALESCE(OLD.description, ''));
END;

-- ============================================================
-- Record migration
-- ============================================================

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES ('005', 'materials_catalog');
