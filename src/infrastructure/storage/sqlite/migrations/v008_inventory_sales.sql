-- v008: Inventory tracking and local sales tables
-- Adds inventory_items, stock_movements, local_sales_invoices, local_sales_items

-- inventory_items table
CREATE TABLE IF NOT EXISTS inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id TEXT NOT NULL,
    quantity_on_hand REAL NOT NULL DEFAULT 0.0,
    avg_cost REAL NOT NULL DEFAULT 0.0,
    last_movement_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES materials(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_material ON inventory_items(material_id);

-- stock_movements table
CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_item_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL CHECK(movement_type IN ('in', 'out', 'adjust')),
    quantity REAL NOT NULL,
    unit_cost REAL NOT NULL DEFAULT 0.0,
    reference TEXT,
    notes TEXT,
    movement_date DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
);
CREATE INDEX IF NOT EXISTS idx_movements_item ON stock_movements(inventory_item_id);
CREATE INDEX IF NOT EXISTS idx_movements_date ON stock_movements(movement_date);

-- local_sales_invoices table
CREATE TABLE IF NOT EXISTS local_sales_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    sale_date DATE NOT NULL,
    subtotal REAL NOT NULL DEFAULT 0.0,
    tax_amount REAL NOT NULL DEFAULT 0.0,
    total_amount REAL NOT NULL DEFAULT 0.0,
    total_cost REAL NOT NULL DEFAULT 0.0,
    total_profit REAL NOT NULL DEFAULT 0.0,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sales_inv_date ON local_sales_invoices(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_inv_number ON local_sales_invoices(invoice_number);

-- local_sales_items table
CREATE TABLE IF NOT EXISTS local_sales_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sales_invoice_id INTEGER NOT NULL,
    inventory_item_id INTEGER NOT NULL,
    material_id TEXT NOT NULL,
    description TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit_price REAL NOT NULL,
    cost_basis REAL NOT NULL DEFAULT 0.0,
    line_total REAL NOT NULL DEFAULT 0.0,
    profit REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sales_invoice_id) REFERENCES local_sales_invoices(id),
    FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id),
    FOREIGN KEY (material_id) REFERENCES materials(id)
);
CREATE INDEX IF NOT EXISTS idx_sales_items_invoice ON local_sales_items(sales_invoice_id);

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES ('008', 'inventory_sales');
