# SRG API Reference

Base URL: `http://localhost:8000`

All endpoints are prefixed with `/api` unless otherwise noted.

---

## Health

### `GET /api/health`

Basic health check.

**Response** `200 OK`

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600.0
}
```

### `GET /api/health/full`

Full system health including all providers.

**Response** `200 OK`

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600.0,
  "llm": { "name": "ollama", "available": true, "latency_ms": 45.2 },
  "embedding": { "name": "bge-m3", "available": true, "latency_ms": 12.1 },
  "database": { "name": "sqlite", "available": true, "latency_ms": 1.3 },
  "vector_store": { "name": "faiss", "available": true, "latency_ms": 0.5 }
}
```

### `GET /api/health/llm`

LLM provider health.

### `GET /api/health/db`

Database connectivity check.

### `GET /api/health/search`

Vector store and FTS5 health.

---

## Chat

### `POST /api/chat`

Send a chat message with optional RAG context.

**Request Body**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `message` | `string` | *required* | User message (1-4000 chars) |
| `session_id` | `string\|null` | `null` | Session UUID to continue conversation. Creates new session if `null` |
| `use_rag` | `boolean` | `true` | Retrieve relevant document context before responding |
| `top_k` | `integer` | `5` | Number of context chunks for RAG (1-20) |
| `max_context_length` | `integer` | `4000` | Max context chars (500-16000) |
| `stream` | `boolean` | `false` | If `true`, redirects to streaming endpoint |
| `include_sources` | `boolean` | `true` | Include source citations in response |
| `extract_memory` | `boolean` | `true` | Extract and store memory facts |

**Example Request**

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What was the total from VOLTA HUB last month?",
    "use_rag": true,
    "top_k": 5
  }'
```

**Response** `200 OK`

```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": {
    "id": "msg_001",
    "role": "assistant",
    "content": "Based on the invoices I found...",
    "created_at": "2026-01-27T10:00:00Z",
    "context_used": "Invoice #VH-2024-001...",
    "token_count": 245
  },
  "context_chunks": 3,
  "citations": [
    {
      "document_id": "doc_001",
      "chunk_id": "chunk_042",
      "file_name": "VOLTA_HUB_Jan2026.pdf",
      "page_number": 1,
      "relevance_score": 0.92,
      "snippet": "Total Amount: USD 15,420.00"
    }
  ],
  "memory_updates": [
    {
      "fact_type": "entity",
      "content": "User interested in VOLTA HUB invoices",
      "confidence": 0.85
    }
  ],
  "is_new_session": true
}
```

### `POST /api/chat/stream`

Stream chat response via Server-Sent Events (SSE).

**Request Body**: Same as `POST /api/chat`.

**Response**: `text/event-stream`

```
data: Based on
data:  the invoices
data:  I found...
data: [DONE]
```

Error during streaming:

```
data: [ERROR] LLM provider unavailable
```

**Example (JavaScript)**

```javascript
const response = await fetch('/api/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'Hello', stream: true }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const lines = decoder.decode(value).split('\n');
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = line.slice(6);
      if (data === '[DONE]') return;
      if (data.startsWith('[ERROR]')) throw new Error(data);
      process.stdout.write(data);
    }
  }
}
```

### `GET /api/chat/context`

Preview RAG context for a query without generating a response.

**Query Parameters**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | `string` | *required* | Search query |
| `top_k` | `integer` | `5` | Number of chunks |

**Response** `200 OK`

```json
{
  "query": "PVC cable prices",
  "context": "From VOLTA_HUB_Jan2026.pdf:\n...",
  "chunks": 3
}
```

---

## Sessions

### `POST /api/sessions`

Create a new chat session.

**Request Body**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `title` | `string\|null` | `null` | Session title (max 200 chars) |
| `metadata` | `object\|null` | `null` | Arbitrary metadata |

**Response** `201 Created`

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Invoice Discussion",
  "message_count": 0,
  "created_at": "2026-01-27T10:00:00Z",
  "updated_at": "2026-01-27T10:00:00Z",
  "metadata": {}
}
```

### `GET /api/sessions`

List all chat sessions.

**Response** `200 OK`

```json
{
  "sessions": [
    {
      "id": "a1b2c3d4-...",
      "title": "Invoice Discussion",
      "message_count": 12,
      "created_at": "2026-01-27T10:00:00Z",
      "updated_at": "2026-01-27T11:30:00Z",
      "metadata": {}
    }
  ],
  "total": 1
}
```

### `GET /api/sessions/{session_id}`

Get session details.

### `DELETE /api/sessions/{session_id}`

Delete a session and all its messages.

### `GET /api/sessions/{session_id}/messages`

Get all messages in a session.

**Response** `200 OK`

```json
{
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": "What invoices do we have from VOLTA HUB?",
      "created_at": "2026-01-27T10:00:00Z",
      "context_used": null,
      "token_count": 12
    },
    {
      "id": "msg_002",
      "role": "assistant",
      "content": "I found 3 invoices from VOLTA HUB...",
      "created_at": "2026-01-27T10:00:05Z",
      "context_used": "Context from 3 chunks...",
      "token_count": 187
    }
  ]
}
```

### `GET /api/sessions/{session_id}/summary`

Generate an AI summary of the session conversation.

---

## Search

### `POST /api/search`

Full search with configurable strategy.

**Request Body**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | `string` | *required* | Search query (1-500 chars) |
| `top_k` | `integer` | `5` | Results to return (1-50) |
| `search_type` | `string` | `"hybrid"` | `"hybrid"`, `"semantic"`, or `"keyword"` |
| `use_reranker` | `boolean` | `true` | Apply neural reranking |
| `use_cache` | `boolean` | `true` | Use cached results |
| `filters` | `object\|null` | `null` | Metadata filters, e.g. `{"vendor": "VOLTA HUB"}` |
| `min_score` | `float` | `0.0` | Minimum relevance threshold (0-1) |

**Example Request**

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "PVC cable 4mm prices",
    "top_k": 10,
    "search_type": "hybrid",
    "use_reranker": true
  }'
```

**Response** `200 OK`

```json
{
  "query": "PVC cable 4mm prices",
  "results": [
    {
      "chunk_id": "chunk_042",
      "document_id": "doc_001",
      "content": "PVC Insulated Cable 4mm x 100m - Unit Price: 12.50 AED...",
      "score": 0.94,
      "metadata": { "vendor": "VOLTA HUB", "page": 1 },
      "page_number": 1,
      "file_name": "VOLTA_HUB_Jan2026.pdf",
      "highlight": "PVC Insulated Cable <mark>4mm</mark> x 100m..."
    }
  ],
  "total": 5,
  "search_type": "hybrid",
  "took_ms": 145.3,
  "cache_hit": false,
  "reranked": true
}
```

### `GET /api/search/quick`

Quick search via GET.

**Query Parameters**: `q` (required), `top_k` (default 5)

### `POST /api/search/semantic`

Pure vector (semantic) search only.

### `POST /api/search/keyword`

Pure FTS5 (keyword) search only.

### `GET /api/search/cache/stats`

Cache hit/miss statistics.

### `POST /api/search/cache/invalidate`

Clear search cache.

---

## Invoices

### `POST /api/invoices/upload`

Upload and parse an invoice file.

**Content-Type**: `multipart/form-data`

**Form Fields**

| Field | Type | Description |
|-------|------|-------------|
| `file` | `File` | PDF, PNG, JPG, or JPEG file (max 50MB) |

**Query Parameters**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `vendor_hint` | `string` | `null` | Vendor name hint for template matching |
| `template_id` | `string` | `null` | Force specific template |
| `source` | `string` | `null` | Source: `"email"`, `"scan"`, `"manual_upload"` |
| `auto_audit` | `boolean` | `true` | Run audit after parsing |
| `auto_index` | `boolean` | `true` | Index for search |
| `strict_mode` | `boolean` | `false` | Fail on warnings |

**Example Request**

```bash
curl -X POST http://localhost:8000/api/invoices/upload \
  -F "file=@invoice.pdf" \
  -F "vendor_hint=VOLTA HUB" \
  -F "auto_audit=true"
```

**Response** `200 OK`

```json
{
  "document_id": "doc_001",
  "invoice_id": "inv_001",
  "invoice": {
    "id": "inv_001",
    "invoice_number": "VH-2026-0042",
    "vendor_name": "VOLTA HUB ELECTRICAL TRADING",
    "buyer_name": "AL REEM CONTRACTING",
    "invoice_date": "2026-01-15",
    "due_date": "2026-02-15",
    "subtotal": 14500.00,
    "tax_amount": 725.00,
    "total_amount": 15225.00,
    "currency": "AED",
    "line_items": [
      {
        "description": "PVC Insulated Cable 4mm x 100m",
        "quantity": 50.0,
        "unit": "roll",
        "unit_price": 125.00,
        "total_price": 6250.00,
        "hs_code": "8544.49",
        "reference": null
      }
    ],
    "calculated_total": 15225.00,
    "source_file": "invoice.pdf",
    "parsed_at": "2026-01-27T10:00:00Z",
    "confidence": 0.95,
    "parser_used": "template_parser"
  },
  "confidence": 0.95,
  "warnings": [],
  "audit": {
    "id": "audit_001",
    "invoice_id": "inv_001",
    "passed": true,
    "confidence": 0.98,
    "findings": [],
    "summary": "All checks passed. Invoice is valid.",
    "audited_at": "2026-01-27T10:00:01Z",
    "error_count": 0,
    "warning_count": 0,
    "llm_used": true,
    "duration_ms": 1250.0
  },
  "indexed": true
}
```

### `GET /api/invoices`

List invoices with pagination.

**Query Parameters**: `limit` (default 50), `offset` (default 0)

**Response** `200 OK`

```json
{
  "invoices": [ ... ],
  "total": 42
}
```

### `GET /api/invoices/{invoice_id}`

Get invoice details including line items.

### `DELETE /api/invoices/{invoice_id}`

Delete an invoice.

### `POST /api/invoices/{invoice_id}/audit`

Run audit on an existing invoice.

**Request Body**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `invoice_id` | `string` | *required* | Invoice ID |
| `use_llm` | `boolean` | `true` | Use LLM for semantic analysis |
| `strict_mode` | `boolean` | `false` | Treat warnings as errors |
| `rules` | `string[]\|null` | `null` | Specific rules to check (all if null) |
| `save_result` | `boolean` | `true` | Persist audit result |

**Response** `200 OK`: `AuditResult` object (see Upload response).

### `GET /api/invoices/{invoice_id}/audits`

Get audit history for an invoice.

---

## Documents

### `POST /api/documents/upload`

Upload and index a document for search.

**Content-Type**: `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `file` | `File` | PDF, TXT, or MD file |

### `POST /api/documents/index`

Index a document from a local file path.

**Request Body**

```json
{
  "file_path": "/path/to/document.pdf",
  "metadata": { "category": "contracts" }
}
```

### `POST /api/documents/index-directory`

Bulk index all documents in a directory.

**Request Body**

```json
{
  "directory": "/path/to/invoices",
  "recursive": true,
  "extensions": [".pdf", ".txt"]
}
```

### `GET /api/documents`

List indexed documents with pagination.

**Query Parameters**: `limit` (default 50), `offset` (default 0)

### `GET /api/documents/{document_id}`

Get document details including chunk/page counts.

### `POST /api/documents/{document_id}/reindex`

Reprocess and reindex a document.

### `DELETE /api/documents/{document_id}`

Delete a document and its index data.

### `GET /api/documents/stats`

Indexing statistics.

**Response** `200 OK`

```json
{
  "documents": 42,
  "chunks": 1250,
  "vectors": 1250,
  "index_synced": true
}
```

---

## Error Responses

All errors follow a consistent format:

```json
{
  "error": "InvoiceNotFoundError",
  "detail": "Invoice with ID 'inv_999' not found",
  "code": "INVOICE_NOT_FOUND",
  "path": "/api/invoices/inv_999",
  "timestamp": "2026-01-27T10:00:00Z"
}
```

### Error Codes

| HTTP Status | Error | Description |
|-------------|-------|-------------|
| `400` | `ValidationError` | Invalid request body or parameters |
| `404` | `DocumentNotFoundError` | Document ID not found |
| `404` | `InvoiceNotFoundError` | Invoice ID not found |
| `404` | `SessionNotFoundError` | Session ID not found |
| `409` | `DuplicateDocumentError` | File already indexed (same hash) |
| `500` | `ParsingError` | Invoice parsing failed |
| `500` | `AuditError` | Audit processing failed |
| `500` | `LLMError` | LLM provider error |
| `503` | `LLMError` | LLM provider unavailable (circuit breaker open) |
