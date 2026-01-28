-- Migration: v006_matched_material_id
-- Description: Add matched_material_id column to invoice_items for catalog linking
-- Version: 1.4.0
-- Created: 2026-01-27
-- Dependencies: v005_materials_catalog

-- ============================================================
-- Add matched_material_id to invoice_items
-- ============================================================

ALTER TABLE invoice_items ADD COLUMN matched_material_id TEXT REFERENCES materials(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_invoice_items_material ON invoice_items(matched_material_id);

-- ============================================================
-- Record migration
-- ============================================================

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES ('006', 'matched_material_id');
