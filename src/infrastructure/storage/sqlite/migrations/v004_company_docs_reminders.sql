-- Migration: v004_company_docs_reminders
-- Description: Add company documents with expiry tracking and reminders
-- Version: 1.3.0
-- Created: 2026-01-27
-- Dependencies: v003_materials

-- ============================================================
-- Company Documents Table
-- ============================================================

CREATE TABLE IF NOT EXISTS company_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_key TEXT NOT NULL,
    title TEXT NOT NULL,
    document_type TEXT NOT NULL DEFAULT 'other',
    file_path TEXT,
    doc_id INTEGER,
    expiry_date DATE,
    issued_date DATE,
    issuer TEXT,
    notes TEXT,
    metadata_json TEXT DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_company_docs_company_key ON company_documents(company_key);
CREATE INDEX IF NOT EXISTS idx_company_docs_expiry ON company_documents(expiry_date);

-- ============================================================
-- Reminders Table
-- ============================================================

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    message TEXT DEFAULT '',
    due_date DATE NOT NULL,
    is_done INTEGER NOT NULL DEFAULT 0,
    linked_entity_type TEXT,
    linked_entity_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reminders_due_date ON reminders(due_date);
CREATE INDEX IF NOT EXISTS idx_reminders_is_done ON reminders(is_done);

-- ============================================================
-- Record migration
-- ============================================================

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES ('004', 'company_docs_reminders');
