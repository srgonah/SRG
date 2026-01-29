# Catalog Flow

How invoice line items become materials in the catalog.

---

## Workflow

```
1. Upload Invoice          POST /api/invoices/upload
       |
       v
2. Audit Invoice           POST /api/invoices/{id}/audit
       |
       v
3. View Invoice Detail     GET  /api/invoices/{id}
   (items show matched_material_id, needs_catalog, catalog_suggestions)
       |
       v
4a. View Unmatched Items   GET  /api/invoices/{id}/items/unmatched
    (focused list with FTS5 suggestions)
       |
       v
4b. Auto-Match to Catalog  POST /api/invoices/{id}/match-catalog
    (matches items against existing catalog entries)
       |
       v
4c. Manual Match           POST /api/invoices/{id}/items/{item_id}/match
    (link single item to specific material)
       |
       v
4d. Add Unmatched to       POST /api/catalog/
    Catalog                body: { "invoice_id": N, "item_ids": [10, 11] }
       |
       v
5. Verify                  GET  /api/invoices/{id}     -> items now matched
                           GET  /api/catalog/           -> materials listed
                           GET  /api/prices/stats       -> price stats populated
```

---

## Step-by-Step

### 1. Upload an invoice

```bash
curl -X POST http://localhost:8000/api/invoices/upload \
  -F "file=@invoice.pdf" \
  -F "auto_audit=true"
```

Response includes `invoice_id`. The upload parses the PDF, extracts line
items, and (if `auto_audit=true`) runs the rule-based + LLM audit.

A SQLite trigger (`trg_item_price_history`) automatically inserts each
`line_item` row into `item_price_history` at upload time.

### 2. View the invoice detail

```bash
curl http://localhost:8000/api/invoices/{invoice_id}
```

Each line item in the response now includes:

| Field | Type | Description |
|-------|------|-------------|
| `matched_material_id` | `string \| null` | Material ID if already cataloged |
| `needs_catalog` | `bool` | `true` when the item is a line item with no matched material |
| `catalog_suggestions` | `list` | Top 5 candidate materials from FTS5 search |

Example item:

```json
{
  "description": "PVC Cable 10mm",
  "quantity": 100,
  "unit": "M",
  "unit_price": 5.0,
  "total_price": 500.0,
  "hs_code": "8544.42",
  "matched_material_id": null,
  "needs_catalog": true,
  "catalog_suggestions": [
    {
      "material_id": "abc-123",
      "name": "PVC Cable 10mm",
      "normalized_name": "pvc cable 10mm",
      "hs_code": "8544.42",
      "unit": "M"
    }
  ]
}
```

### 3. View unmatched items with suggestions

Get a focused list of unmatched items with FTS5-based catalog suggestions:

```bash
curl http://localhost:8000/api/invoices/{invoice_id}/items/unmatched
```

Response:

```json
{
  "invoice_id": "1",
  "total_items": 5,
  "unmatched_count": 2,
  "items": [
    {
      "item_id": 10,
      "invoice_id": 1,
      "item_name": "PVC Cable 10mm",
      "description": null,
      "quantity": 100,
      "unit": "M",
      "unit_price": 5.0,
      "hs_code": "8544.42",
      "brand": null,
      "suggestions": [
        {
          "material_id": "abc-123",
          "name": "PVC Cable 10mm",
          "normalized_name": "pvc cable 10mm",
          "hs_code": "8544.42",
          "unit": "M"
        }
      ]
    }
  ]
}
```

### 4. Auto-match against existing catalog

Attempt to automatically match items against existing catalog entries:

```bash
curl -X POST http://localhost:8000/api/invoices/{invoice_id}/match-catalog
```

This finds exact matches (by normalized name or synonym) and links them
without creating new materials. Items that can't be matched remain unmatched.

Response:

```json
{
  "invoice_id": "1",
  "total_items": 5,
  "matched": 3,
  "unmatched": 2,
  "results": [
    {
      "item_id": 10,
      "item_name": "PVC Cable 10mm",
      "matched": true,
      "material_id": "abc-123"
    }
  ]
}
```

### 5. Manual match a single item

Link a specific item to a specific material:

```bash
curl -X POST http://localhost:8000/api/invoices/{invoice_id}/items/{item_id}/match \
  -H "Content-Type: application/json" \
  -d '{"material_id": "abc-123"}'
```

Response:

```json
{
  "item_id": 10,
  "invoice_id": 1,
  "item_name": "PVC Cable 10mm",
  "matched_material_id": "abc-123",
  "material_name": "PVC Cable 10mm"
}
```

### 6. Add selected items to the catalog

Pick the items with `needs_catalog: true` and call:

```bash
curl -X POST http://localhost:8000/api/catalog/ \
  -H "Content-Type: application/json" \
  -d '{"invoice_id": 1, "item_ids": [10, 11]}'
```

Omit `item_ids` to catalog **all** line items in the invoice.

The use case (`AddToCatalogUseCase`) does the following for each item:

1. Normalizes the item name (`strip().lower()`)
2. Searches for an existing material by `normalized_name` or synonym
3. If found: reuses the existing material, adds a new synonym if the raw
   description differs, backfills missing `hs_code` or `unit`
4. If not found: creates a new `Material` entry
5. Links price history rows to the material via `material_id`
6. Sets `matched_material_id` on the invoice item

Response:

```json
{
  "materials_created": 1,
  "materials_updated": 1,
  "materials": [
    {
      "id": "abc-123",
      "name": "PVC Cable 10mm",
      "normalized_name": "pvc cable 10mm",
      "hs_code": "8544.42",
      "unit": "M"
    }
  ]
}
```

### 4. Verify

Re-fetch the invoice detail:

```bash
curl http://localhost:8000/api/invoices/{invoice_id}
```

Items that were cataloged now have `matched_material_id` set and
`needs_catalog: false`.

Browse the catalog:

```bash
# List all materials
curl http://localhost:8000/api/catalog/

# Search
curl "http://localhost:8000/api/catalog/?q=cable"

# Material detail with synonyms
curl http://localhost:8000/api/catalog/{material_id}
```

Check price statistics:

```bash
curl "http://localhost:8000/api/prices/stats?item=pvc+cable"
curl "http://localhost:8000/api/prices/history?item=pvc+cable&seller=ACME"
```

---

## Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/invoices/upload` | Upload + parse + auto-audit |
| GET | `/api/invoices/{id}` | Invoice detail with catalog info per item |
| GET | `/api/invoices/{id}/items/unmatched` | List unmatched items with FTS5 suggestions |
| POST | `/api/invoices/{id}/audit` | Audit invoice |
| POST | `/api/invoices/{id}/match-catalog` | Auto-match items to existing catalog |
| POST | `/api/invoices/{id}/items/{item_id}/match` | Manual match item to material |
| POST | `/api/catalog/` | Add invoice items to catalog (creates new materials) |
| GET | `/api/catalog/` | List/search materials |
| GET | `/api/catalog/{material_id}` | Material detail + synonyms |
| GET | `/api/prices/history` | Price history (filters: item, seller, dates) |
| GET | `/api/prices/stats` | Price statistics per item |

---

## Data Flow

```
invoice_items
    |
    +-- matched_material_id --> materials
    |                            |
    |                            +-- material_synonyms
    |
    +-- (trigger on INSERT) --> item_price_history
                                    |
                                    +-- material_id (set by AddToCatalog)
                                    |
                                    v
                               v_item_price_stats (view)
```

---

## Deduplication

The catalog deduplicates materials automatically:

- On `POST /api/catalog/`, each item is checked against `materials.normalized_name`
  and `material_synonyms.synonym` before creating a new entry.
- When the same item appears across multiple invoices, only one `Material`
  record exists. Additional invoice descriptions are added as synonyms.
- Price history rows from all invoices link to the same `material_id`.
