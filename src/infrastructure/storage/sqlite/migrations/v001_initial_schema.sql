-- Migration: v001_initial_schema
-- Description: Initial database schema for SRG Invoice Processing System
-- Version: 1.0.0
-- Created: 2026-01-25

-- Enable required pragmas
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;  -- 64MB cache
PRAGMA temp_store = MEMORY;

-- ============================================================
-- SECTION 1: Documents and Indexing
-- ============================================================

-- Main documents table
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT,
    file_size INTEGER DEFAULT 0,
    mime_type TEXT DEFAULT 'application/pdf',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'indexed', 'failed')),
    error_message TEXT,
    version INTEGER DEFAULT 1,
    is_latest INTEGER DEFAULT 1 CHECK(is_latest IN (0, 1)),
    previous_version_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    page_count INTEGER DEFAULT 0,
    company_key TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    indexed_at TEXT
);

-- Document indexes
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company_key);
CREATE INDEX IF NOT EXISTS idx_documents_latest ON documents(is_latest) WHERE is_latest = 1;
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at DESC);

-- Document pages table
CREATE TABLE IF NOT EXISTS doc_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no INTEGER NOT NULL,
    page_type TEXT DEFAULT 'other' CHECK(page_type IN (
        'invoice', 'packing_list', 'contract', 'bank_form',
        'certificate', 'cover_letter', 'other'
    )),
    type_confidence REAL DEFAULT 0.0 CHECK(type_confidence >= 0.0 AND type_confidence <= 1.0),
    text TEXT,
    text_length INTEGER DEFAULT 0,
    image_path TEXT,
    image_hash TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(doc_id, page_no)
);

CREATE INDEX IF NOT EXISTS idx_pages_doc ON doc_pages(doc_id);
CREATE INDEX IF NOT EXISTS idx_pages_type ON doc_pages(page_type);

-- Document chunks for vector search
CREATE TABLE IF NOT EXISTS doc_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_id INTEGER REFERENCES doc_pages(id) ON DELETE CASCADE,
    chunk_index INTEGER DEFAULT 0,
    chunk_text TEXT NOT NULL,
    chunk_size INTEGER DEFAULT 0,
    start_char INTEGER DEFAULT 0,
    end_char INTEGER DEFAULT 0,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON doc_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_page ON doc_chunks(page_id);
CREATE INDEX IF NOT EXISTS idx_chunks_index ON doc_chunks(doc_id, chunk_index);

-- FTS5 virtual table for chunk full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS doc_chunks_fts USING fts5(
    chunk_text,
    content='doc_chunks',
    content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 1'
);

-- FTS5 sync triggers for doc_chunks
CREATE TRIGGER IF NOT EXISTS doc_chunks_ai AFTER INSERT ON doc_chunks BEGIN
    INSERT INTO doc_chunks_fts(rowid, chunk_text) VALUES (new.id, new.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS doc_chunks_ad AFTER DELETE ON doc_chunks BEGIN
    INSERT INTO doc_chunks_fts(doc_chunks_fts, rowid, chunk_text)
    VALUES ('delete', old.id, old.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS doc_chunks_au AFTER UPDATE ON doc_chunks BEGIN
    INSERT INTO doc_chunks_fts(doc_chunks_fts, rowid, chunk_text)
    VALUES ('delete', old.id, old.chunk_text);
    INSERT INTO doc_chunks_fts(rowid, chunk_text) VALUES (new.id, new.chunk_text);
END;

-- FAISS ID mapping for chunks (Index A)
CREATE TABLE IF NOT EXISTS doc_chunks_faiss_map (
    faiss_id INTEGER PRIMARY KEY,
    chunk_id INTEGER NOT NULL REFERENCES doc_chunks(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chunks_faiss_chunk ON doc_chunks_faiss_map(chunk_id);

-- ============================================================
-- SECTION 2: Invoices and Line Items
-- ============================================================

-- Main invoices table
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    invoice_no TEXT,
    invoice_date TEXT,
    seller_name TEXT,
    buyer_name TEXT,
    company_key TEXT,
    currency TEXT DEFAULT 'USD',
    total_amount REAL DEFAULT 0.0,
    subtotal REAL DEFAULT 0.0,
    tax_amount REAL DEFAULT 0.0,
    discount_amount REAL DEFAULT 0.0,
    total_quantity REAL DEFAULT 0.0,
    quality_score REAL DEFAULT 0.0 CHECK(quality_score >= 0.0 AND quality_score <= 1.0),
    confidence REAL DEFAULT 0.0 CHECK(confidence >= 0.0 AND confidence <= 1.0),
    template_confidence REAL DEFAULT 0.0,
    parser_version TEXT DEFAULT 'v1.0',
    template_id TEXT,
    parsing_status TEXT DEFAULT 'ok' CHECK(parsing_status IN ('ok', 'partial', 'failed', 'needs_review')),
    error_message TEXT,
    bank_details_json TEXT,
    is_latest INTEGER DEFAULT 1 CHECK(is_latest IN (0, 1)),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Invoice indexes
CREATE INDEX IF NOT EXISTS idx_invoices_doc ON invoices(doc_id);
CREATE INDEX IF NOT EXISTS idx_invoices_no ON invoices(invoice_no);
CREATE INDEX IF NOT EXISTS idx_invoices_company ON invoices(company_key);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_latest ON invoices(is_latest) WHERE is_latest = 1;
CREATE INDEX IF NOT EXISTS idx_invoices_seller ON invoices(seller_name);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(parsing_status);

-- Invoice line items table
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    line_number INTEGER DEFAULT 0,
    item_name TEXT NOT NULL,
    description TEXT,
    hs_code TEXT,
    unit TEXT,
    brand TEXT,
    model TEXT,
    quantity REAL DEFAULT 0.0,
    unit_price REAL DEFAULT 0.0,
    total_price REAL DEFAULT 0.0,
    row_type TEXT DEFAULT 'line_item' CHECK(row_type IN ('line_item', 'header', 'summary', 'subtotal')),
    created_at TEXT DEFAULT (datetime('now'))
);

-- Item indexes
CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_items_name ON invoice_items(item_name);
CREATE INDEX IF NOT EXISTS idx_items_hs ON invoice_items(hs_code);
CREATE INDEX IF NOT EXISTS idx_items_type ON invoice_items(row_type);
CREATE INDEX IF NOT EXISTS idx_items_line ON invoice_items(invoice_id, line_number);

-- FTS5 virtual table for item full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS invoice_items_fts USING fts5(
    item_name,
    description,
    hs_code,
    content='invoice_items',
    content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 1'
);

-- FTS5 sync triggers for invoice_items
CREATE TRIGGER IF NOT EXISTS invoice_items_ai AFTER INSERT ON invoice_items BEGIN
    INSERT INTO invoice_items_fts(rowid, item_name, description, hs_code)
    VALUES (new.id, new.item_name, COALESCE(new.description, ''), COALESCE(new.hs_code, ''));
END;

CREATE TRIGGER IF NOT EXISTS invoice_items_ad AFTER DELETE ON invoice_items BEGIN
    INSERT INTO invoice_items_fts(invoice_items_fts, rowid, item_name, description, hs_code)
    VALUES ('delete', old.id, old.item_name, COALESCE(old.description, ''), COALESCE(old.hs_code, ''));
END;

CREATE TRIGGER IF NOT EXISTS invoice_items_au AFTER UPDATE ON invoice_items BEGIN
    INSERT INTO invoice_items_fts(invoice_items_fts, rowid, item_name, description, hs_code)
    VALUES ('delete', old.id, old.item_name, COALESCE(old.description, ''), COALESCE(old.hs_code, ''));
    INSERT INTO invoice_items_fts(rowid, item_name, description, hs_code)
    VALUES (new.id, new.item_name, COALESCE(new.description, ''), COALESCE(new.hs_code, ''));
END;

-- FAISS ID mapping for items (Index B)
CREATE TABLE IF NOT EXISTS line_items_faiss_map (
    faiss_id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES invoice_items(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_items_faiss_item ON line_items_faiss_map(item_id);

-- ============================================================
-- SECTION 3: Audit Results (9-Section Report)
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    trace_id TEXT NOT NULL UNIQUE,
    success INTEGER DEFAULT 1 CHECK(success IN (0, 1)),
    audit_type TEXT DEFAULT 'llm' CHECK(audit_type IN ('llm', 'rule_based_fallback')),
    status TEXT DEFAULT 'HOLD' CHECK(status IN ('PASS', 'HOLD', 'FAIL', 'ERROR')),
    filename TEXT,

    -- 9 Report Sections (JSON)
    document_intake_json TEXT,       -- Section 1
    proforma_summary_json TEXT,      -- Section 2
    items_table_json TEXT,           -- Section 3
    arithmetic_check_json TEXT,      -- Section 4
    amount_words_check_json TEXT,    -- Section 5
    bank_details_check_json TEXT,    -- Section 6
    commercial_terms_json TEXT,      -- Section 7
    contract_summary_json TEXT,      -- Section 8
    final_verdict_json TEXT,         -- Section 9

    issues_json TEXT,
    processing_time REAL DEFAULT 0.0,
    llm_model TEXT,
    confidence REAL DEFAULT 0.0,
    error_message TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_invoice ON audit_results(invoice_id);
CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_results(trace_id);
CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_results(status);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_results(created_at DESC);

-- ============================================================
-- SECTION 4: Chat Sessions and Memory
-- ============================================================

-- Chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    title TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'archived', 'deleted')),
    company_key TEXT,
    active_doc_ids_json TEXT DEFAULT '[]',
    active_invoice_ids_json TEXT DEFAULT '[]',
    conversation_summary TEXT,
    summary_message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    max_context_tokens INTEGER DEFAULT 8000,
    system_prompt TEXT,
    temperature REAL DEFAULT 0.7 CHECK(temperature >= 0.0 AND temperature <= 2.0),
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    last_message_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_id ON chat_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON chat_sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_company ON chat_sessions(company_key);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC);

-- Chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    message_type TEXT DEFAULT 'text' CHECK(message_type IN (
        'text', 'search_query', 'search_result', 'document_ref', 'error'
    )),
    search_query TEXT,
    search_results_json TEXT,
    sources_json TEXT DEFAULT '[]',
    token_count INTEGER DEFAULT 0,
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_role ON chat_messages(role);
CREATE INDEX IF NOT EXISTS idx_messages_created ON chat_messages(created_at);

-- Memory facts table (long-term context)
CREATE TABLE IF NOT EXISTS memory_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES chat_sessions(session_id) ON DELETE SET NULL,
    fact_type TEXT NOT NULL CHECK(fact_type IN (
        'user_preference', 'document_context', 'entity', 'relationship', 'temporal'
    )),
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0 CHECK(confidence >= 0.0 AND confidence <= 1.0),
    related_doc_ids_json TEXT DEFAULT '[]',
    related_invoice_ids_json TEXT DEFAULT '[]',
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT,
    UNIQUE(session_id, key)
);

CREATE INDEX IF NOT EXISTS idx_facts_session ON memory_facts(session_id);
CREATE INDEX IF NOT EXISTS idx_facts_type ON memory_facts(fact_type);
CREATE INDEX IF NOT EXISTS idx_facts_key ON memory_facts(key);
CREATE INDEX IF NOT EXISTS idx_facts_expires ON memory_facts(expires_at) WHERE expires_at IS NOT NULL;

-- ============================================================
-- SECTION 5: Company Templates
-- ============================================================

CREATE TABLE IF NOT EXISTS company_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT UNIQUE NOT NULL,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    template_version INTEGER DEFAULT 1,
    template_yaml TEXT NOT NULL,
    detection_patterns_json TEXT,
    parser_hints_json TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1 CHECK(is_active IN (0, 1)),
    sample_doc_ids_json TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_templates_company ON company_templates(company_key);
CREATE INDEX IF NOT EXISTS idx_templates_active ON company_templates(is_active) WHERE is_active = 1;
CREATE UNIQUE INDEX IF NOT EXISTS idx_templates_company_active ON company_templates(company_key)
    WHERE is_active = 1;

-- ============================================================
-- SECTION 6: Indexing State (Incremental Indexing)
-- ============================================================

CREATE TABLE IF NOT EXISTS indexing_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_name TEXT UNIQUE NOT NULL CHECK(index_name IN ('chunks', 'items')),
    last_doc_id INTEGER DEFAULT 0,
    last_chunk_id INTEGER DEFAULT 0,
    last_item_id INTEGER DEFAULT 0,
    total_indexed INTEGER DEFAULT 0,
    pending_count INTEGER DEFAULT 0,
    is_building INTEGER DEFAULT 0 CHECK(is_building IN (0, 1)),
    last_error TEXT,
    last_run_at TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Initialize indexing state for both indexes
INSERT OR IGNORE INTO indexing_state (index_name) VALUES ('chunks');
INSERT OR IGNORE INTO indexing_state (index_name) VALUES ('items');

-- ============================================================
-- SECTION 7: Schema Migrations Tracking
-- ============================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT DEFAULT (datetime('now')),
    checksum TEXT,
    execution_time_ms INTEGER
);

-- Record this migration
INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES ('001', 'initial_schema');

-- ============================================================
-- SECTION 8: Utility Views
-- ============================================================

-- View: Recent documents with invoice status
CREATE VIEW IF NOT EXISTS v_documents_with_invoices AS
SELECT
    d.id AS doc_id,
    d.filename,
    d.original_filename,
    d.status AS doc_status,
    d.company_key,
    d.page_count,
    d.created_at AS doc_created_at,
    i.id AS invoice_id,
    i.invoice_no,
    i.invoice_date,
    i.total_amount,
    i.parsing_status,
    ar.status AS audit_status
FROM documents d
LEFT JOIN invoices i ON d.id = i.doc_id AND i.is_latest = 1
LEFT JOIN audit_results ar ON i.id = ar.invoice_id
WHERE d.is_latest = 1
ORDER BY d.created_at DESC;

-- View: Search results helper (chunks with document info)
CREATE VIEW IF NOT EXISTS v_searchable_chunks AS
SELECT
    c.id AS chunk_id,
    c.doc_id,
    c.chunk_text,
    c.chunk_index,
    d.filename,
    d.company_key,
    p.page_no,
    p.page_type
FROM doc_chunks c
JOIN documents d ON c.doc_id = d.id AND d.is_latest = 1
LEFT JOIN doc_pages p ON c.page_id = p.id;

-- View: Search results helper (items with invoice info)
CREATE VIEW IF NOT EXISTS v_searchable_items AS
SELECT
    it.id AS item_id,
    it.invoice_id,
    it.item_name,
    it.description,
    it.hs_code,
    it.quantity,
    it.unit_price,
    it.total_price,
    inv.invoice_no,
    inv.invoice_date,
    inv.seller_name,
    inv.company_key,
    d.filename
FROM invoice_items it
JOIN invoices inv ON it.invoice_id = inv.id AND inv.is_latest = 1
LEFT JOIN documents d ON inv.doc_id = d.id
WHERE it.row_type = 'line_item';

-- View: Audit summary
CREATE VIEW IF NOT EXISTS v_audit_summary AS
SELECT
    ar.id AS audit_id,
    ar.invoice_id,
    ar.trace_id,
    ar.status,
    ar.audit_type,
    ar.processing_time,
    ar.llm_model,
    ar.created_at,
    inv.invoice_no,
    inv.seller_name,
    d.filename
FROM audit_results ar
JOIN invoices inv ON ar.invoice_id = inv.id
LEFT JOIN documents d ON inv.doc_id = d.id
ORDER BY ar.created_at DESC;

-- ============================================================
-- SECTION 9: Auto-Update Triggers
-- ============================================================

-- Trigger: Auto-update updated_at on documents
CREATE TRIGGER IF NOT EXISTS trg_documents_updated_at
AFTER UPDATE ON documents
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE documents SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Trigger: Auto-update updated_at on invoices
CREATE TRIGGER IF NOT EXISTS trg_invoices_updated_at
AFTER UPDATE ON invoices
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE invoices SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Trigger: Auto-update updated_at on chat_sessions
CREATE TRIGGER IF NOT EXISTS trg_sessions_updated_at
AFTER UPDATE ON chat_sessions
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Trigger: Auto-update updated_at on memory_facts
CREATE TRIGGER IF NOT EXISTS trg_facts_updated_at
AFTER UPDATE ON memory_facts
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE memory_facts SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Trigger: Auto-update last_message_at on session when message added
CREATE TRIGGER IF NOT EXISTS trg_session_last_message
AFTER INSERT ON chat_messages
FOR EACH ROW
BEGIN
    UPDATE chat_sessions
    SET last_message_at = NEW.created_at,
        updated_at = datetime('now')
    WHERE session_id = NEW.session_id;
END;

-- Trigger: Cascade is_latest=0 when new document version created
CREATE TRIGGER IF NOT EXISTS trg_documents_version
AFTER INSERT ON documents
FOR EACH ROW
WHEN NEW.previous_version_id IS NOT NULL
BEGIN
    UPDATE documents SET is_latest = 0 WHERE id = NEW.previous_version_id;
END;
