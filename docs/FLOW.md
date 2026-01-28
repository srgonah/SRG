# SRG Runtime Pipeline

Audited: 2026-01-27. Evidence: live server on :8000, 730 passing tests, 6 applied migrations,
53 OpenAPI endpoints across 10 routers.

---

## How to Run

```bash
# Migrations (6 applied: v001..v006, 36 tables)
srg-migrate
# or: python -m src.infrastructure.storage.sqlite.migrations.migrator

# Server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
# or: .\tools\restart_server.ps1

# Tests (730 pass, 4 known failures in company-doc/reminder detail/delete)
pytest -v

# Lint
ruff check src tests
```

---

## Implementation Status

| Feature                         | Code | Store | Routes | Tests | Live |
|---------------------------------|------|-------|--------|-------|------|
| Invoice upload + parse          | done | SQLiteInvoiceStore | POST /api/invoices/upload | done | 200 |
| Invoice audit (rules + LLM)    | done | audit_results table | POST /api/invoices/{id}/audit | done | 200 |
| Proforma PDF generation         | done | Fpdf2ProformaRenderer | POST /api/invoices/{id}/proforma-pdf | done | 200 |
| Materials catalog               | done | SQLiteMaterialStore | POST,GET /api/catalog | done | 200* |
| Price history + stats           | done | SQLitePriceHistoryStore | GET /api/prices/history,stats | done | 200* |
| Company documents + expiry      | done | SQLiteCompanyDocumentStore | CRUD /api/company-documents | done | 200 |
| Reminders                       | done | SQLiteReminderStore | CRUD /api/reminders | done | 200 |
| Document indexing + RAG search  | done | FAISSVectorStore + FTS5 | POST /api/search | done | 200 |
| Chat with RAG context           | done | SQLiteSessionStore | POST /api/chat | done | 200 |
| Session management              | done | SQLiteSessionStore | CRUD /api/sessions | done | 200 |

*Catalog and prices routes were changed from `/api/v1/` to `/api/` in Milestone C.
A stale uvicorn process still serves the old prefix; restart to pick up the change.

---

## CURRENT Flow (what runs today)

```
                           SRG CURRENT PIPELINE
                           ====================

 PDF/Image File
      |
      v
 +--------------------+     +-----------------+     +------------------+
 | POST               |     | InvoiceParser   |     | SQLite           |
 | /api/invoices/     |---->| Service         |---->| InvoiceStore     |
 | upload             |     | (strategy       |     | (invoices +      |
 |                    |     |  registry)      |     |  invoice_items + |
 +--------------------+     +------+----------+     |  audit_results)  |
                                   |                +--------+---------+
                                   | auto_audit=true         |
                                   v                         |
                            +----------------+               |
                            | InvoiceAuditor |               |
                            | Service        |               |
                            | (rules + LLM)  |               |
                            +------+---------+               |
                                   |                         |
                                   | save audit              |
                                   +----------->-------------+
                                                             |
      +------------------------------------------------------+
      |
      v
 +--------------------+     +-----------------+     +------------------+
 | POST               |     | AddToCatalog    |     | SQLite           |
 | /api/catalog/      |---->| UseCase         |---->| MaterialStore    |
 | {invoice_id,       |     | - normalize     |     | (materials +     |
 |  item_ids?}        |     | - find/create   |     |  synonyms +      |
 +--------------------+     | - link price    |     |  materials_fts)  |
                            | - set matched_  |     +------------------+
                            |   material_id   |              |
                            +-----------------+              |
                                   |                         |
                                   v                         |
                            +------------------+             |
                            | SQLite           |             |
                            | PriceHistory     |<- trigger --+
                            | Store            |   (on item insert)
                            | (item_price_     |
                            |  history +       |
                            |  v_item_price_   |
                            |  stats view)     |
                            +------------------+

 +--------------------+     +-----------------+     +------------------+
 | POST               |     | GenerateProforma|     | Fpdf2Proforma    |
 | /api/invoices/     |---->| PdfUseCase      |---->| Renderer         |
 | {id}/proforma-pdf  |     |                 |     | (fpdf2 lib)      |
 +--------------------+     +-----------------+     +------------------+
                                                          |
                                                          v
                                                    PDF bytes returned
                                                    as StreamingResponse


 +--------------------+     +-----------------+     +------------------+
 | POST /api/search   |     | SearchService   |     | FAISS + FTS5     |
 |                    |---->| (hybrid search  |---->| HybridSearcher   |
 | POST /api/chat     |     |  with RRF       |     | + BGE Reranker   |
 |                    |     |  fusion)        |     +------------------+
 +--------------------+     +--------+--------+
                                     |
                                     v
                            +-----------------+
                            | ChatService     |
                            | (LLM generate   |
                            |  with RAG       |
                            |  context)       |
                            +-----------------+
                                     |
                                     v
                            +-----------------+
                            | Ollama /        |
                            | llama.cpp       |
                            | (circuit        |
                            |  breaker)       |
                            +-----------------+


 +--------------------+     +-----------------+
 | CRUD               |     | SQLiteCompany   |
 | /api/company-      |---->| DocumentStore   |
 | documents          |     | (expiry         |
 +--------------------+     |  tracking)      |
                            +-----------------+

 +--------------------+     +-----------------+
 | CRUD               |     | SQLiteReminder  |
 | /api/reminders     |---->| Store           |
 +--------------------+     | (due dates)     |
                            +-----------------+
```

### Data layer (SQLite, 36 tables)

```
documents ─┬─ doc_pages ─── doc_chunks ─── doc_chunks_fts
            \                                  \
             doc_chunks_faiss_map               doc_chunks_faiss_map

invoices ──── invoice_items ─── invoice_items_fts
                   |                \
                   |                 line_items_faiss_map
                   |
                   +-- matched_material_id --> materials
                   |                           |
                   +-- (trigger) ------------> item_price_history
                                               |
                                               v
                                         v_item_price_stats (view)

materials ─── material_synonyms
              materials_fts

company_documents    (company_key + expiry_date)
reminders            (due_date + linked_entity)
chat_sessions ─── chat_messages ─── memory_facts
audit_results        (linked to invoices)
indexing_state       (incremental index tracker)
schema_migrations    (v001..v006)
```

---

## TARGET Flow (planned improvements)

```
                           SRG TARGET PIPELINE
                           ====================

 PDF/Image File
      |
      v
 +--------------------+     +-----------------+     +------------------+
 | POST               |     | InvoiceParser   |     | SQLiteInvoice    |
 | /api/invoices/     |---->| Service         |---->| Store            |
 | upload             |     | (strategy       |     +--------+---------+
 +--------------------+     |  registry)      |              |
                            +------+----------+              |
                                   |                         |
            +----------------------+-----------+             |
            |  auto_audit=true                 |             |
            v                                  v             |
 +-----------------+               +-----------------+       |
 | InvoiceAuditor  |               | Auto-Catalog    |       |
 | Service         |               | (future)        |       |
 | (rules + LLM)   |               | auto-match new  |       |
 +--------+--------+               | items to exist- |       |
          |                        | ing materials   |       |
          v                        | using fuzzy +   |       |
   audit_results                   | embedding match |       |
                                   +---------+-------+       |
                                             |               |
                                             v               |
                                   +------------------+      |
                                   | MaterialStore    |<-----+
                                   | (auto-link       |
                                   |  matched_        |
                                   |  material_id     |
                                   |  on upload)      |
                                   +------------------+
                                             |
                                             v
                                   +------------------+
                                   | Improved Audit   |
                                   | - price anomaly  |
                                   |   detection vs   |
                                   |   historical     |
                                   |   avg from       |
                                   |   v_item_price_  |
                                   |   stats          |
                                   | - duplicate item |
                                   |   detection      |
                                   |   across invoices|
                                   | - material-level |
                                   |   audit rules    |
                                   +------------------+

 +--------------------+     +-----------------+
 | GET                |     | Dashboard       |
 | /api/company-      |     | (future)        |
 | documents/expiring |---->| - expiry alerts |
 |                    |     | - reminder push |
 | GET                |     | - price trends  |
 | /api/reminders/    |     |   per material  |
 | upcoming           |     +-----------------+
 +--------------------+
```

### Planned enhancements (not yet implemented)

| Enhancement | Depends On | Notes |
|-------------|-----------|-------|
| Auto-catalog on upload | MaterialStore + embedding similarity | Match `item_name` to existing `materials.normalized_name` using vector cosine similarity before creating new material |
| Price anomaly audit rule | v_item_price_stats view | Flag line items where `unit_price` deviates >20% from historical `avg_price` for the same normalized item |
| Cross-invoice duplicate detection | item_price_history | Warn when same item+seller appears in two invoices within N days |
| Expiry alert integration | company_documents.expiry_date + reminders | Auto-create reminder when a company document is within 30 days of expiry |
| Material-level audit rules | materials + matched_material_id | Validate HS code consistency, unit consistency across invoices for the same material |

---

## Endpoint Map (53 endpoints, 10 routers)

### Core Business

```
POST   /api/invoices/upload                  Upload + parse + auto-audit
GET    /api/invoices                         List invoices
GET    /api/invoices/{id}                    Get invoice detail
DELETE /api/invoices/{id}                    Delete invoice
POST   /api/invoices/{id}/audit              Audit invoice
GET    /api/invoices/{id}/audits             Audit history
POST   /api/invoices/{id}/proforma-pdf       Generate proforma PDF
```

### Materials Catalog

```
POST   /api/catalog/                         Add invoice items to catalog
GET    /api/catalog/                          List materials (search: ?q=)
GET    /api/catalog/{material_id}             Material detail + synonyms
```

### Price History

```
GET    /api/prices/history                   Price history (filters: item_name, seller, dates)
GET    /api/prices/stats                     Price statistics per item
```

### Company Documents

```
POST   /api/company-documents                Create document record
GET    /api/company-documents                List (filter: ?company_key=)
GET    /api/company-documents/expiring       Expiring within N days
GET    /api/company-documents/{id}           Detail
PUT    /api/company-documents/{id}           Update
DELETE /api/company-documents/{id}           Delete
```

### Reminders

```
POST   /api/reminders                        Create reminder
GET    /api/reminders                        List (filter: ?include_done=)
GET    /api/reminders/upcoming               Due within N days
GET    /api/reminders/{id}                   Detail
PUT    /api/reminders/{id}                   Update / mark done
DELETE /api/reminders/{id}                   Delete
```

### Document Indexing

```
POST   /api/documents/upload                 Upload + index document
POST   /api/documents/index                  Index by file path
POST   /api/documents/index-directory        Index directory recursively
GET    /api/documents                        List documents
GET    /api/documents/stats                  Indexing statistics
GET    /api/documents/{id}                   Document detail
POST   /api/documents/{id}/reindex           Re-index document
DELETE /api/documents/{id}                   Delete + remove from index
```

### Search

```
POST   /api/search                           Hybrid search (vector + FTS5 + RRF)
GET    /api/search/quick                     Quick search (GET convenience)
POST   /api/search/semantic                  Pure vector search
POST   /api/search/keyword                   Pure FTS5 search
GET    /api/search/cache/stats               Cache statistics
POST   /api/search/cache/invalidate          Clear cache
```

### Chat (RAG)

```
POST   /api/chat                             Chat with RAG context
POST   /api/chat/stream                      Streaming chat (SSE)
GET    /api/chat/context                     Debug: get RAG context for query
```

### Sessions

```
POST   /api/sessions                         Create session
GET    /api/sessions                         List sessions
GET    /api/sessions/{id}                    Get session
DELETE /api/sessions/{id}                    Delete session
GET    /api/sessions/{id}/messages           Message history
GET    /api/sessions/{id}/summary            Generate summary
```

### Health

```
GET    /api/health                           Basic health (status + uptime)
GET    /api/health/db                        Database connectivity
GET    /api/health/llm                       LLM provider status
GET    /api/health/search                    Vector store status
GET    /api/health/full                      All components
GET    /api/health/detailed                  Alias for /full
```

---

## Audit Finding

**Stale server prefix**: The live server (pid started before Milestone C) still
serves catalog at `/api/v1/catalog/` and prices at `/api/v1/prices/`. Source code
is correct (`/api/catalog`, `/api/prices`). Fix: restart uvicorn via
`.\tools\restart_server.ps1` or see `docs/TROUBLESHOOTING.md`.
