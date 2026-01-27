-- Migration: v002_price_history
-- Description: Add price history tracking for items
-- Version: 1.1.0
-- Created: 2026-01-25
-- Dependencies: v001_initial_schema

-- ============================================================
-- Price History Table (for LLM auditor price trend analysis)
-- ============================================================

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
    created_at TEXT DEFAULT (datetime('now'))
);

-- Indexes for price trend queries
CREATE INDEX IF NOT EXISTS idx_price_history_item ON item_price_history(item_name_normalized);
CREATE INDEX IF NOT EXISTS idx_price_history_hs ON item_price_history(hs_code);
CREATE INDEX IF NOT EXISTS idx_price_history_seller ON item_price_history(seller_name);
CREATE INDEX IF NOT EXISTS idx_price_history_date ON item_price_history(invoice_date);
CREATE INDEX IF NOT EXISTS idx_price_history_invoice ON item_price_history(invoice_id);
CREATE INDEX IF NOT EXISTS idx_price_history_lookup ON item_price_history(
    item_name_normalized, seller_name, invoice_date DESC
);

-- ============================================================
-- Trigger: Auto-populate price history on item insert
-- ============================================================

CREATE TRIGGER IF NOT EXISTS trg_item_price_history
AFTER INSERT ON invoice_items
FOR EACH ROW
WHEN NEW.row_type = 'line_item' AND NEW.unit_price > 0
BEGIN
    INSERT INTO item_price_history (
        item_name_normalized,
        hs_code,
        seller_name,
        invoice_id,
        invoice_date,
        quantity,
        unit_price,
        currency
    )
    SELECT
        LOWER(TRIM(NEW.item_name)),
        NEW.hs_code,
        inv.seller_name,
        NEW.invoice_id,
        COALESCE(inv.invoice_date, date('now')),
        NEW.quantity,
        NEW.unit_price,
        inv.currency
    FROM invoices inv
    WHERE inv.id = NEW.invoice_id;
END;

-- ============================================================
-- View: Price statistics by item
-- ============================================================

CREATE VIEW IF NOT EXISTS v_item_price_stats AS
SELECT
    item_name_normalized,
    hs_code,
    seller_name,
    currency,
    COUNT(*) AS occurrence_count,
    MIN(unit_price) AS min_price,
    MAX(unit_price) AS max_price,
    AVG(unit_price) AS avg_price,
    -- Price variance indicator
    CASE
        WHEN MAX(unit_price) = MIN(unit_price) THEN 'stable'
        WHEN (MAX(unit_price) - MIN(unit_price)) / AVG(unit_price) < 0.05 THEN 'stable'
        WHEN (MAX(unit_price) - MIN(unit_price)) / AVG(unit_price) < 0.20 THEN 'moderate'
        ELSE 'volatile'
    END AS price_trend,
    MIN(invoice_date) AS first_seen,
    MAX(invoice_date) AS last_seen
FROM item_price_history
GROUP BY item_name_normalized, hs_code, seller_name, currency;

-- Record this migration
INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES ('002', 'price_history');
