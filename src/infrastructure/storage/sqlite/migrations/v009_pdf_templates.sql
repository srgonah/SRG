-- Migration v009: PDF Templates
-- Adds tables for storing PDF template configurations with customizable layouts

-- PDF Templates table
CREATE TABLE IF NOT EXISTS pdf_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    template_type TEXT NOT NULL DEFAULT 'proforma',  -- proforma, sales, quote, receipt

    -- Asset file paths
    background_path TEXT,
    signature_path TEXT,
    stamp_path TEXT,
    logo_path TEXT,

    -- Layout configuration (JSON)
    positions_json TEXT DEFAULT '{}',

    -- Page settings
    page_size TEXT DEFAULT 'A4',
    orientation TEXT DEFAULT 'portrait',
    margin_top REAL DEFAULT 10.0,
    margin_bottom REAL DEFAULT 10.0,
    margin_left REAL DEFAULT 10.0,
    margin_right REAL DEFAULT 10.0,

    -- Styling
    primary_color TEXT DEFAULT '#000000',
    secondary_color TEXT DEFAULT '#666666',
    header_font_size INTEGER DEFAULT 12,
    body_font_size INTEGER DEFAULT 10,

    -- Flags
    is_default INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,

    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Index for template type lookups
CREATE INDEX IF NOT EXISTS idx_pdf_templates_type ON pdf_templates(template_type);

-- Index for default template lookups
CREATE INDEX IF NOT EXISTS idx_pdf_templates_default ON pdf_templates(template_type, is_default, is_active);

-- Generated documents table (tracks PDFs created from templates)
CREATE TABLE IF NOT EXISTS generated_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_type TEXT NOT NULL,  -- proforma, sales_invoice, quote, etc.
    template_id INTEGER REFERENCES pdf_templates(id) ON DELETE SET NULL,

    -- Source reference (which entity was used to generate)
    source_type TEXT,  -- invoice, sales_invoice, etc.
    source_id INTEGER,

    -- Document metadata
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,

    -- Link to documents table if indexed
    doc_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,

    -- Generation context (JSON)
    context_json TEXT DEFAULT '{}',

    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Index for finding generated documents by source
CREATE INDEX IF NOT EXISTS idx_generated_docs_source ON generated_documents(source_type, source_id);

-- Index for finding generated documents by type
CREATE INDEX IF NOT EXISTS idx_generated_docs_type ON generated_documents(document_type);

-- Insert default templates
INSERT INTO pdf_templates (name, description, template_type, is_default, is_active)
VALUES
    ('Default Proforma', 'Standard proforma invoice template', 'proforma', 1, 1),
    ('Default Sales', 'Standard sales invoice template', 'sales', 1, 1);
