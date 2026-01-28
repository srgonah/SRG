# Inventory & Local Sales Flow

**Phase 10** — Inventory tracking with Weighted Average Cost (WAC) and local sales invoicing with profit calculation.

---

## Entities

### InventoryItem

Tracks stock level and cost basis for a single material.

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-increment PK |
| `material_id` | str | FK → `materials.id` (unique) |
| `quantity_on_hand` | float | Current stock quantity |
| `avg_cost` | float | Weighted Average Cost per unit |
| `last_movement_date` | date | Date of most recent stock movement |
| `created_at` | datetime | Record creation timestamp |
| `updated_at` | datetime | Last update timestamp |

Computed property: `total_value = quantity_on_hand × avg_cost`

### StockMovement

Records every stock change (in, out, or adjustment).

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-increment PK |
| `inventory_item_id` | int | FK → `inventory_items.id` |
| `movement_type` | enum | `in`, `out`, `adjust` |
| `quantity` | float | Always positive |
| `unit_cost` | float | Cost per unit at time of movement |
| `reference` | str? | Invoice number, PO number, etc. |
| `notes` | str? | Free-text notes |
| `movement_date` | date | Date of movement |
| `created_at` | datetime | Record creation timestamp |

### LocalSalesInvoice

A local sales invoice with auto-computed totals.

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-increment PK |
| `invoice_number` | str | Sales invoice number |
| `customer_name` | str | Customer name |
| `sale_date` | date | Date of sale |
| `subtotal` | float | Sum of line totals |
| `tax_amount` | float | Tax amount |
| `total_amount` | float | `subtotal + tax_amount` |
| `total_cost` | float | Sum of item cost bases |
| `total_profit` | float | `total_amount - total_cost` |
| `notes` | str? | Free-text notes |
| `items` | list | Line items |
| `created_at` | datetime | Record creation timestamp |

### LocalSalesItem

A line item on a local sales invoice.

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-increment PK |
| `sales_invoice_id` | int | FK → `local_sales_invoices.id` |
| `inventory_item_id` | int | FK → `inventory_items.id` |
| `material_id` | str | FK → `materials.id` (denormalized) |
| `description` | str | Item description |
| `quantity` | float | Quantity sold |
| `unit_price` | float | Selling price per unit |
| `cost_basis` | float | `avg_cost × quantity` at time of sale |
| `line_total` | float | `quantity × unit_price` |
| `profit` | float | `line_total - cost_basis` |
| `created_at` | datetime | Record creation timestamp |

---

## WAC Formula (Weighted Average Cost)

When receiving new stock:

```
new_avg_cost = (old_qty × old_avg_cost + new_qty × new_unit_cost) / (old_qty + new_qty)
```

Example:
- Existing: 100 units @ $10.00 avg
- Receiving: 50 units @ $12.00
- New avg: (100 × 10 + 50 × 12) / 150 = 1600 / 150 = **$10.67**

When issuing stock, `avg_cost` is unchanged — the cost basis for each issue is `avg_cost × quantity`.

---

## Stock Flow

### Receive Stock (IN)

1. Validate material exists in catalog
2. Get or create `InventoryItem` for the material
3. Recalculate WAC using formula above
4. Update `quantity_on_hand` and `avg_cost`
5. Record `StockMovement(type=IN)`

### Issue Stock (OUT)

1. Get `InventoryItem` by `material_id`
2. Verify `quantity_on_hand >= requested quantity`
3. Deduct `quantity_on_hand` (avg_cost unchanged)
4. Record `StockMovement(type=OUT, unit_cost=current avg_cost)`

### Local Sale

1. For each item in the sales invoice:
   a. Get `InventoryItem` by `material_id`
   b. Check sufficient stock
   c. Calculate `cost_basis = avg_cost × quantity`
   d. Deduct stock and record OUT movement
   e. Build `LocalSalesItem` with profit computation
2. Build `LocalSalesInvoice` (model validator computes totals)
3. Persist invoice and items

---

## API Endpoints

### Inventory

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `POST` | `/api/inventory/receive` | Receive stock (IN movement) | 201 |
| `POST` | `/api/inventory/issue` | Issue stock (OUT movement) | 200 |
| `GET` | `/api/inventory/status` | List all inventory items | 200 |
| `GET` | `/api/inventory/{item_id}/movements` | Get stock movements for item | 200 |

### Sales

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `POST` | `/api/sales/invoices` | Create local sales invoice | 201 |
| `GET` | `/api/sales/invoices` | List sales invoices | 200 |
| `GET` | `/api/sales/invoices/{id}` | Get sales invoice by ID | 200 |

---

## Error Codes

| Code | Exception | Description |
|------|-----------|-------------|
| `INSUFFICIENT_STOCK` | `InsufficientStockError` | Requested quantity exceeds available stock |
| `INVENTORY_ITEM_NOT_FOUND` | `InventoryItemNotFoundError` | No inventory record for the given ID |
| `MATERIAL_NOT_FOUND` | `MaterialNotFoundError` | Material does not exist in catalog |
| `SALES_INVOICE_NOT_FOUND` | `SalesInvoiceNotFoundError` | Sales invoice not found |

---

## Database Tables (v008)

- `inventory_items` — one row per material, tracks qty + WAC
- `stock_movements` — append-only log of all stock changes
- `local_sales_invoices` — sales invoice headers
- `local_sales_items` — sales invoice line items

See `src/infrastructure/storage/sqlite/migrations/v008_inventory_sales.sql`.
