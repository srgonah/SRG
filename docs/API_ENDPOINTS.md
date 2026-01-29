# API Endpoints Reference

Complete list of all API endpoints used by the SRG WebUI.

## Error Response Schema

All error responses follow a consistent schema:

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "hint": "Check the request body fields and types.",
  "path": "/api/invoices/upload",
  "detail": "Optional additional details"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `error_code` | string | Machine-readable error identifier |
| `message` | string | Human-readable error description |
| `hint` | string | Suggested recovery action |
| `path` | string | Request path that caused the error |
| `detail` | string? | Optional additional details |

---

## Health Endpoints

### `GET /api/health`
Basic health check. Returns service status and uptime.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600.5
}
```

### `GET /api/health/full`
Full system health check. Tests LLM, embedding, database, and vector store.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600.5,
  "llm": { "name": "OllamaProvider", "available": true, "latency_ms": 120.5 },
  "embedding": { "name": "HuggingFaceEmbedding", "available": true, "latency_ms": 50.2 },
  "database": { "name": "sqlite", "available": true, "latency_ms": 1.2 },
  "vector_store": { "name": "faiss", "available": true, "latency_ms": 0.5 }
}
```

### `GET /api/health/llm`
LLM provider health check. Safe when LLM is offline (returns `degraded` status).

### `GET /api/health/db`
Database health check. Returns `unhealthy` only if SQLite is unreachable.

### `GET /api/health/search`
Search system health check. Tests vector store availability.

---

## Invoice Endpoints

### `GET /api/invoices`
List invoices with pagination.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Max results |
| `offset` | int | 0 | Skip count |

### `GET /api/invoices/{id}`
Get invoice by ID with line items and catalog suggestions.

### `POST /api/invoices/upload`
Upload and process an invoice (PDF/image).

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `file` | File | required | PDF or image file |
| `vendor_hint` | string? | null | Vendor name hint |
| `template_id` | string? | null | Parser template ID |
| `auto_audit` | bool | true | Run audit after parsing |
| `auto_catalog` | bool | true | Match items to catalog |

### `POST /api/invoices/{id}/audit`
Run audit on an existing invoice.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `use_llm` | bool | true | Include LLM analysis |

### `GET /api/invoices/{id}/audits`
Get audit history for an invoice.

### `POST /api/invoices/{id}/proforma-pdf`
Generate and download proforma PDF.

### `POST /api/invoices/{id}/proforma-preview`
Generate proforma PDF for inline display.

### `POST /api/invoices/{id}/match-catalog`
Auto-match invoice line items to catalog.

### `POST /api/invoices/{id}/items/{item_id}/match`
Manually match an invoice item to a material.

**Body:**
```json
{ "material_id": "MAT-123" }
```

### `DELETE /api/invoices/{id}`
Delete an invoice.

---

## Catalog Endpoints

### `GET /api/catalog`
List materials with optional filtering.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 100 | Max results (1-500) |
| `offset` | int | 0 | Skip count |
| `category` | string? | null | Filter by category |
| `q` | string? | null | Search query |

### `GET /api/catalog/{material_id}`
Get material detail with synonyms.

### `POST /api/catalog`
Add invoice items to the catalog.

### `GET /api/catalog/{material_id}/matches`
Find matching materials for a query.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Item name to match |
| `top_k` | int | 5 | Max candidates |

### `POST /api/catalog/ingest`
Ingest a material from an external URL (e.g., Amazon).

**Body:**
```json
{
  "url": "https://www.amazon.com/dp/B0...",
  "category": "Electronics",
  "unit": "PCS"
}
```

### `POST /api/catalog/ingest/batch`
Batch ingest materials from multiple URLs (max 20).

### `POST /api/catalog/ingest/preview`
Preview parsed product data without saving.

### `GET /api/catalog/export`
Export catalog as JSON or CSV.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | string | "json" | "json" or "csv" |

---

## Price Endpoints

### `GET /api/prices/history`
Query price history with filters.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `item` | string? | null | Item name filter |
| `seller` | string? | null | Seller filter |
| `date_from` | string? | null | Start date (YYYY-MM-DD) |
| `date_to` | string? | null | End date (YYYY-MM-DD) |
| `limit` | int | 100 | Max results |

### `GET /api/prices/stats`
Get price statistics per item/seller.

---

## Company Documents Endpoints

### `GET /api/company-documents`
List company documents.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `company_key` | string? | null | Filter by company |
| `limit` | int | 100 | Max results |
| `offset` | int | 0 | Skip count |

### `GET /api/company-documents/{id}`
Get company document by ID.

### `POST /api/company-documents`
Create a new company document.

**Body:**
```json
{
  "company_key": "ACME-CORP",
  "title": "Business License",
  "document_type": "LICENSE",
  "expiry_date": "2025-12-31",
  "issued_date": "2024-01-01",
  "issuer": "State of California"
}
```

### `PUT /api/company-documents/{id}`
Update a company document.

### `DELETE /api/company-documents/{id}`
Delete a company document.

### `GET /api/company-documents/expiring`
List documents expiring within days.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `within_days` | int | 30 | Days threshold |
| `limit` | int | 100 | Max results |

### `POST /api/company-documents/check-expiry`
Check expiring docs and auto-create reminders.

---

## Reminders Endpoints

### `GET /api/reminders`
List reminders.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `include_done` | bool | false | Include completed |
| `limit` | int | 100 | Max results |
| `offset` | int | 0 | Skip count |

### `GET /api/reminders/{id}`
Get reminder by ID.

### `POST /api/reminders`
Create a new reminder.

**Body:**
```json
{
  "title": "Renew License",
  "message": "Business license expires soon",
  "due_date": "2025-01-15",
  "linked_entity_type": "company_document",
  "linked_entity_id": "42"
}
```

### `PUT /api/reminders/{id}`
Update a reminder.

### `DELETE /api/reminders/{id}`
Delete a reminder.

### `GET /api/reminders/upcoming`
List upcoming reminders.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `within_days` | int | 7 | Days threshold |
| `limit` | int | 100 | Max results |

### `GET /api/reminders/insights`
Evaluate system insights (expiring docs, unmatched items, price anomalies).

---

## Inventory Endpoints

### `GET /api/inventory/status`
Get current inventory status.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 100 | Max results |
| `offset` | int | 0 | Skip count |

### `GET /api/inventory/low-stock`
Get items at or below stock threshold.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold` | float | 10.0 | Stock threshold |
| `limit` | int | 100 | Max results |
| `offset` | int | 0 | Skip count |

### `POST /api/inventory/receive`
Receive stock (IN movement) with WAC recalculation.

**Body:**
```json
{
  "material_id": "MAT-123",
  "quantity": 100,
  "unit_cost": 5.50,
  "reference": "PO-2024-001",
  "notes": "Initial stock"
}
```

### `POST /api/inventory/issue`
Issue stock (OUT movement) with balance check.

**Body:**
```json
{
  "material_id": "MAT-123",
  "quantity": 10,
  "reference": "SALE-001",
  "notes": "Customer order"
}
```

### `GET /api/inventory/{item_id}/movements`
Get stock movements for an item.

---

## Sales Endpoints

### `GET /api/sales/invoices`
List local sales invoices.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 100 | Max results |
| `offset` | int | 0 | Skip count |

### `GET /api/sales/invoices/{id}`
Get sales invoice by ID.

### `POST /api/sales/invoices`
Create a sales invoice, deduct stock, and compute profit.

**Body:**
```json
{
  "invoice_number": "SALE-2024-001",
  "customer_name": "John Doe",
  "sale_date": "2024-01-15",
  "tax_amount": 50.00,
  "notes": "Cash sale",
  "items": [
    {
      "material_id": "MAT-123",
      "description": "Widget A",
      "quantity": 5,
      "unit_price": 25.00
    }
  ]
}
```

### `GET /api/sales/invoices/{id}/pdf`
Generate and download sales invoice PDF.

---

## Documents Endpoints (RAG)

### `GET /api/documents`
List indexed documents.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Max results |
| `offset` | int | 0 | Skip count |

### `GET /api/documents/{id}`
Get document by ID.

### `POST /api/documents/upload`
Upload and index a document (PDF/TXT/MD).

### `POST /api/documents/{id}/reindex`
Reindex an existing document.

### `DELETE /api/documents/{id}`
Delete document and index data.

### `GET /api/documents/stats`
Get indexing statistics.

**Response:**
```json
{
  "documents": 42,
  "chunks": 1250,
  "vectors": 1250,
  "index_synced": true
}
```

---

## Search Endpoints

### `POST /api/search`
Hybrid search (vector + keyword with RRF fusion).

**Body:**
```json
{
  "query": "invoice payment terms",
  "top_k": 10,
  "search_type": "hybrid",
  "use_reranker": true,
  "filters": { "document_id": "123" }
}
```

### `GET /api/search/quick`
Quick search via GET.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | required | Search query |
| `top_k` | int | 5 | Max results |

### `POST /api/search/semantic`
Pure vector (semantic) search.

### `POST /api/search/keyword`
FTS5 keyword search.

### `GET /api/search/cache/stats`
Get search cache statistics.

### `POST /api/search/cache/invalidate`
Clear search cache.

---

## Chat Endpoints

### `POST /api/chat`
Send a chat message with RAG context.

**Body:**
```json
{
  "message": "What are the payment terms?",
  "session_id": "uuid-string",
  "use_rag": true,
  "include_sources": true,
  "stream": false
}
```

### `POST /api/chat/stream`
Stream a chat response (SSE).

### `GET /api/chat/context`
Debug: get context for a query.

---

## Session Endpoints

### `GET /api/sessions`
List chat sessions.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Max results |
| `offset` | int | 0 | Skip count |

### `GET /api/sessions/{id}`
Get session by ID.

### `POST /api/sessions`
Create a new chat session.

**Body:**
```json
{
  "title": "Invoice Questions"
}
```

### `DELETE /api/sessions/{id}`
Delete a chat session.

### `GET /api/sessions/{id}/messages`
Get messages for a session.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max results |

### `GET /api/sessions/{id}/summary`
Generate session summary.

---

## Error Codes Reference

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `INVOICE_NOT_FOUND` | 404 | Invoice ID not found |
| `DOCUMENT_NOT_FOUND` | 404 | Document ID not found |
| `SESSION_NOT_FOUND` | 404 | Session ID not found |
| `MATERIAL_NOT_FOUND` | 404 | Material ID not found |
| `REMINDER_NOT_FOUND` | 404 | Reminder ID not found |
| `COMPANY_DOCUMENT_NOT_FOUND` | 404 | Company document not found |
| `PARSING_FAILED` | 422 | Invoice parsing failed |
| `LLM_UNAVAILABLE` | 503 | LLM provider offline |
| `LLM_TIMEOUT` | 503 | LLM request timed out |
| `CIRCUIT_BREAKER_OPEN` | 503 | Too many LLM failures |
| `DATABASE_ERROR` | 500 | Database operation failed |
| `EMBEDDING_ERROR` | 500 | Embedding generation failed |
