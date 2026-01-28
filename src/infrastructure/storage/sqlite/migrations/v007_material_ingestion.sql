-- Migration: v007_material_ingestion
-- Description: Add ingestion fields to materials table for external product intelligence
-- Version: 1.4.0
-- Created: 2026-01-28
-- Dependencies: v006_matched_material_id

-- ============================================================
-- Add ingestion columns to materials table
-- ============================================================

ALTER TABLE materials ADD COLUMN source_url TEXT;
ALTER TABLE materials ADD COLUMN origin_country TEXT;
ALTER TABLE materials ADD COLUMN origin_confidence TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE materials ADD COLUMN evidence_text TEXT;
ALTER TABLE materials ADD COLUMN brand TEXT;

-- ============================================================
-- Index for origin filtering
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_materials_origin_country ON materials(origin_country);
CREATE INDEX IF NOT EXISTS idx_materials_origin_confidence ON materials(origin_confidence);

-- ============================================================
-- Record migration
-- ============================================================

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES ('007', 'material_ingestion');
