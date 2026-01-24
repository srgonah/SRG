-- SRG Database Schema
-- Version: 1.0.0
-- Single SQLite database with all tables

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================
-- Documents and Indexing
-- ============================================================

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT,
    file_size INTEGER DEFAULT 0,
    mime_type TEXT DEFAULT 'application/pdf',
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    version INTEGER DEFAULT 1,
    is_latest INTEGER DEFAULT 1,
    previous_version_id INTEGER REFERENCES documents(id),
    page_count INTEGER DEFAULT 0,
    company_key TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    indexed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company_key);
CREATE INDEX IF NOT EXISTS idx_documents_latest ON documents(is_latest);

CREATE TABLE IF NOT EXISTS doc_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no INTEGER NOT NULL,
    page_type TEXT DEFAULT 'other',
    type_confidence REAL DEFAULT 0.0,
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

-- FTS5 for chunk full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS doc_chunks_fts USING fts5(
    chunk_text,
    content='doc_chunks',
    content_rowid='id'
);

-- FAISS ID mapping for chunks
CREATE TABLE IF NOT EXISTS doc_chunks_faiss_map (
    faiss_id INTEGER PRIMARY KEY,
    chunk_id INTEGER NOT NULL REFERENCES doc_chunks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_faiss_chunk ON doc_chunks_faiss_map(chunk_id);

-- ============================================================
-- Invoices and Items
-- ============================================================

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
    quality_score REAL DEFAULT 0.0,
    confidence REAL DEFAULT 0.0,
    template_confidence REAL DEFAULT 0.0,
    parser_version TEXT DEFAULT 'v1.0',
    template_id TEXT,
    parsing_status TEXT DEFAULT 'ok',
    error_message TEXT,
    bank_details_json TEXT,
    is_latest INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_invoices_doc ON invoices(doc_id);
CREATE INDEX IF NOT EXISTS idx_invoices_no ON invoices(invoice_no);
CREATE INDEX IF NOT EXISTS idx_invoices_company ON invoices(company_key);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_latest ON invoices(is_latest);

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
    row_type TEXT DEFAULT 'line_item',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_items_name ON invoice_items(item_name);
CREATE INDEX IF NOT EXISTS idx_items_hs ON invoice_items(hs_code);
CREATE INDEX IF NOT EXISTS idx_items_type ON invoice_items(row_type);

-- FTS5 for item full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS invoice_items_fts USING fts5(
    item_name,
    description,
    hs_code,
    content='invoice_items',
    content_rowid='id'
);

-- FAISS ID mapping for items
CREATE TABLE IF NOT EXISTS line_items_faiss_map (
    faiss_id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES invoice_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_items_faiss_item ON line_items_faiss_map(item_id);

-- ============================================================
-- Audit Results
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    trace_id TEXT NOT NULL,
    success INTEGER DEFAULT 1,
    audit_type TEXT DEFAULT 'llm',
    status TEXT DEFAULT 'HOLD',
    filename TEXT,
    document_intake_json TEXT,
    proforma_summary_json TEXT,
    items_table_json TEXT,
    arithmetic_check_json TEXT,
    amount_words_check_json TEXT,
    bank_details_check_json TEXT,
    commercial_terms_json TEXT,
    contract_summary_json TEXT,
    final_verdict_json TEXT,
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

-- ============================================================
-- Chat Sessions
-- ============================================================

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    title TEXT,
    status TEXT DEFAULT 'active',
    company_key TEXT,
    active_doc_ids_json TEXT,
    active_invoice_ids_json TEXT,
    conversation_summary TEXT,
    summary_message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    max_context_tokens INTEGER DEFAULT 8000,
    system_prompt TEXT,
    temperature REAL DEFAULT 0.7,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    last_message_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_id ON chat_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON chat_sessions(status);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    message_type TEXT DEFAULT 'text',
    search_query TEXT,
    search_results_json TEXT,
    sources_json TEXT,
    token_count INTEGER DEFAULT 0,
    metadata_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_role ON chat_messages(role);

CREATE TABLE IF NOT EXISTS memory_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES chat_sessions(session_id) ON DELETE SET NULL,
    fact_type TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    related_doc_ids_json TEXT,
    related_invoice_ids_json TEXT,
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_facts_session ON memory_facts(session_id);
CREATE INDEX IF NOT EXISTS idx_facts_type ON memory_facts(fact_type);
CREATE INDEX IF NOT EXISTS idx_facts_key ON memory_facts(key);

-- ============================================================
-- Company Templates
-- ============================================================

CREATE TABLE IF NOT EXISTS company_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT UNIQUE NOT NULL,
    company_key TEXT NOT NULL,
    company_name TEXT NOT NULL,
    template_version INTEGER DEFAULT 1,
    template_yaml TEXT NOT NULL,
    detection_patterns_json TEXT,
    parser_hints_json TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_templates_company ON company_templates(company_key);
CREATE INDEX IF NOT EXISTS idx_templates_active ON company_templates(is_active);

-- ============================================================
-- Indexing State (for incremental indexing)
-- ============================================================

CREATE TABLE IF NOT EXISTS indexing_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_name TEXT UNIQUE NOT NULL,
    last_doc_id INTEGER DEFAULT 0,
    last_chunk_id INTEGER DEFAULT 0,
    last_item_id INTEGER DEFAULT 0,
    total_indexed INTEGER DEFAULT 0,
    pending_count INTEGER DEFAULT 0,
    is_building INTEGER DEFAULT 0,
    last_error TEXT,
    last_run_at TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- Schema Version
-- ============================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_version (version) VALUES ('1.0.0');
