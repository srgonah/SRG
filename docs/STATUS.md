# SRG Progress Audit — STATUS.md

**Updated**: 2026-01-28 (final close-out)
**Commit scope**: Full `src/`, `tests/`, tooling audit
**Tool results**: pytest 916 pass (804 non-API + 112 API) | ruff 0 errors | mypy 0 errors (140 files)

---

## 1. What Works Now

### 1.1 Core Domain Layer (`src/core/`)

| Feature | Files | Key Classes/Functions | Status |
|---------|-------|----------------------|--------|
| Invoice entity model | `core/entities/invoice.py` | `Invoice`, `LineItem`, `AuditResult`, `AuditIssue`, `ArithmeticCheck` | Complete |
| Document entity model | `core/entities/document.py` | `Document`, `Page`, `Chunk`, `SearchResult`, `IndexingState` | Complete |
| Session/Chat entity model | `core/entities/session.py` | `ChatSession`, `Message`, `MemoryFact` | Complete |
| **Material entity** | `core/entities/material.py` | `Material`, `MaterialSynonym`, `OriginConfidence`, auto-normalized name, ingestion fields (brand, source_url, origin_country, evidence_text) | Complete |
| **Company document entity** | `core/entities/company_document.py` | `CompanyDocument`, `CompanyDocumentType`, `.is_expired`, `.days_until_expiry()` | Complete |
| **Reminder entity** | `core/entities/reminder.py` | `Reminder`, `.is_overdue` | Complete |
| **Inventory entity** | `core/entities/inventory.py` | `InventoryItem` (WAC, total_value), `StockMovement`, `MovementType` (IN/OUT/ADJUST) | Complete |
| **Local sales entity** | `core/entities/local_sale.py` | `LocalSalesInvoice` (auto-totals/profit), `LocalSalesItem` (line_total, cost_basis, profit) | Complete |
| Exception hierarchy | `core/exceptions.py` | `SRGError` → `StorageError`, `LLMError`, `ParserError`, `SearchError`, `AuditError`, `ChatError`, `IndexingError`, `InvoiceNotFoundError`, `InventoryError`, `InsufficientStockError`, `SalesError` | Complete |
| Storage interfaces (ABCs) | `core/interfaces/storage.py` | `IDocumentStore`, `IInvoiceStore`, `ISessionStore`, `IVectorStore`, `IHybridSearcher`, `IReranker`, `ISearchCache`, `ICompanyDocumentStore`, `IReminderStore`, `IInventoryStore`, `ISalesStore` | Complete |
| **Material store interface** | `core/interfaces/material_store.py` | `IMaterialStore` — 9 abstract methods (CRUD + synonym + FTS search) | Complete |
| **Price history interface** | `core/interfaces/price_history.py` | `IPriceHistoryStore` — `get_price_history`, `get_price_stats`, `link_material` | Complete |
| LLM interfaces | `core/interfaces/llm.py` | `ILLMProvider`, `IVisionProvider`, `IEmbeddingProvider` | Complete |
| Parser interfaces | `core/interfaces/parser.py` | `IInvoiceParser`, `ITemplateDetector`, `ITextExtractor`, `IParserRegistry` | Complete |
| Chat service | `core/services/chat_service.py` | `ChatService.create_session()`, `.send_message()`, `.stream_response()`, `.extract_memory_facts()` | Complete |
| Search service | `core/services/search_service.py` | `SearchService.search()`, `.search_items()`, `.prepare_context()` | Complete |
| Invoice parser service | `core/services/invoice_parser.py` | `InvoiceParserService.parse_invoice()`, `.parse_page()` | Complete |
| Invoice auditor service | `core/services/invoice_auditor.py` | `InvoiceAuditorService.audit_invoice()`, `_check_math()`, `_check_required_fields()`, `_check_bank_details()`, `_check_format()`, `_check_price_anomalies()`, `_check_cross_invoice_duplicates()`, `_llm_semantic_analysis()` | Complete |
| Document indexer service | `core/services/document_indexer.py` | `DocumentIndexerService.index_document()`, `.index_incremental()`, `.rebuild_index_full()` | Complete |
| **Proforma PDF service** | `core/services/proforma_pdf_service.py` | `IProformaPdfRenderer`, `ProformaPdfService`, `ProformaPdfResult` | Complete |
| **Material ingestion service** | `core/services/material_ingestion.py` | `MaterialIngestionService`, `IngestionResult` — orchestrates URL fetching, dedup, create/update | Complete |
| **Product page fetcher interface** | `core/interfaces/product_fetcher.py` | `IProductPageFetcher`, `ProductPageData` — abstract interface for e-commerce scraping | Complete |

### 1.2 Infrastructure Layer (`src/infrastructure/`)

| Feature | Files | Status |
|---------|-------|--------|
| Ollama LLM provider + circuit breaker | `infrastructure/llm/ollama.py`, `infrastructure/llm/base.py` | Complete |
| llama-cpp LLM provider | `infrastructure/llm/llama_cpp.py` | Complete |
| BGE-M3 embedding provider | `infrastructure/embeddings/bge_m3.py` | Complete |
| Template-based parser (priority 100) | `infrastructure/parsers/template_parser.py` | Complete |
| Table-aware parser (priority 80) | `infrastructure/parsers/table_aware_parser.py` | Complete |
| Vision parser fallback (priority 60) | `infrastructure/parsers/vision_parser.py` | Complete |
| Parser registry (strategy chain) | `infrastructure/parsers/registry.py` | Complete |
| SQLite document store | `infrastructure/storage/sqlite/document_store.py` | Complete |
| SQLite invoice store | `infrastructure/storage/sqlite/invoice_store.py` | Complete |
| SQLite session store | `infrastructure/storage/sqlite/session_store.py` | Complete |
| **SQLite material store** | `infrastructure/storage/sqlite/material_store.py` | Complete (CRUD + FTS5 search + synonym management) |
| **SQLite price history store** | `infrastructure/storage/sqlite/price_history_store.py` | Complete (queries `item_price_history` + `v_item_price_stats` view) |
| **SQLite company document store** | `infrastructure/storage/sqlite/company_document_store.py` | Complete |
| **SQLite reminder store** | `infrastructure/storage/sqlite/reminder_store.py` | Complete |
| **SQLite inventory store** | `infrastructure/storage/sqlite/inventory_store.py` | Complete (CRUD + movement tracking) |
| **SQLite sales store** | `infrastructure/storage/sqlite/sales_store.py` | Complete (invoice + items in transaction) |
| **Fpdf2 proforma PDF renderer** | `infrastructure/pdf/fpdf2_renderer.py` | Complete |
| **Amazon product fetcher** | `infrastructure/scrapers/amazon_fetcher.py` | Complete — supports amazon.ae/com/co.uk/de/fr/sa, JSON-LD + HTML parsing, origin detection |
| FAISS vector store (chunks + items indexes) | `infrastructure/storage/vector/faiss_store.py` | Complete |
| SQLite FTS5 keyword search | `infrastructure/search/fts.py` | Complete |
| Hybrid searcher (FAISS + FTS + RRF) | `infrastructure/search/hybrid.py` | Complete |
| Reranker (BGE-reranker-v2-m3) | `infrastructure/search/reranker.py` | Complete |
| Database migrations v001 (initial schema) | `migrations/v001_initial_schema.sql` | Complete |
| Database migrations v002 (price history) | `migrations/v002_price_history.sql` | Complete — trigger + view + app code |
| Database migrations v003 (materials) | `migrations/v003_materials.sql` | Complete |
| Database migrations v004 (company docs + reminders) | `migrations/v004_company_docs_reminders.sql` | Complete |
| **Database migrations v005 (materials catalog)** | `migrations/v005_materials_catalog.sql` | Complete — FTS5 + sync triggers |
| **Database migrations v006 (matched_material_id)** | `migrations/v006_matched_material_id.sql` | Complete — FK on invoice_items |
| **Database migrations v007 (material ingestion)** | `migrations/v007_material_ingestion.sql` | Complete — source_url, origin_country, origin_confidence, evidence_text, brand columns + indexes |
| **Database migrations v008 (inventory & sales)** | `migrations/v008_inventory_sales.sql` | Complete — inventory_items, stock_movements, local_sales_invoices, local_sales_items + indexes |
| Memory + disk caching | `infrastructure/cache/memory_cache.py`, `disk_cache.py` | Complete |

### 1.3 Application Layer (`src/application/`)

| Use Case | File | Status |
|----------|------|--------|
| Upload Invoice | `application/use_cases/upload_invoice.py` | Complete |
| Audit Invoice | `application/use_cases/audit_invoice.py` | Complete |
| Search Documents | `application/use_cases/search_documents.py` | Complete |
| Chat With Context (RAG) | `application/use_cases/chat_with_context.py` | Complete |
| **Generate Proforma PDF** | `application/use_cases/generate_proforma_pdf.py` | Complete |
| **Add to Catalog** | `application/use_cases/add_to_catalog.py` | Complete — find/create material, synonyms, link price history, set matched_material_id, `auto_match_items()` for upload |
| **Ingest Material** | `application/use_cases/ingest_material.py` | Complete — ingest from external URL, extract brand/origin/synonyms |
| **Check Expiring Documents** | `application/use_cases/check_expiring_documents.py` | Complete — scans expiring docs, creates reminders for un-reminded ones, `ExpiryCheckResult` dataclass |
| **Receive Stock** | `application/use_cases/receive_stock.py` | Complete — WAC recalculation, create-or-update inventory item, IN movement |
| **Issue Stock** | `application/use_cases/issue_stock.py` | Complete — balance check, deduct stock, OUT movement |
| **Create Sales Invoice** | `application/use_cases/create_sales_invoice.py` | Complete — multi-item deduction, cost basis, profit calculation |
| DTOs (request/response) | `application/dto/requests.py`, `responses.py` | Complete (includes catalog, price, company docs, reminders, proforma, catalog suggestions, expiry check, inventory, sales) |
| Service factory (singletons) | `application/services.py` | Complete |

### 1.4 API Layer — 53 paths, 12 Routers (confirmed from live openapi.json)

| Router | File | Endpoints |
|--------|------|-----------|
| Health | `api/routes/health.py` | `GET /api/health`, `/llm`, `/db`, `/search`, `/full`, `/detailed` |
| Invoices | `api/routes/invoices.py` | `POST /upload`, `POST /{id}/audit`, `POST /{id}/proforma-pdf`, `GET/DELETE /{id}`, `GET /`, `GET /{id}/audits` |
| **Catalog** | `api/routes/catalog.py` | `POST /api/catalog/`, `GET /api/catalog/`, `GET /api/catalog/{material_id}`, `POST /api/catalog/ingest` |
| **Prices** | `api/routes/prices.py` | `GET /api/prices/history`, `GET /api/prices/stats` |
| Documents | `api/routes/documents.py` | `POST /upload`, `POST /index`, `POST /index-directory`, `GET /`, `GET /stats`, `GET/DELETE /{id}`, `POST /{id}/reindex` |
| Search | `api/routes/search.py` | `POST /search`, `GET /quick`, `POST /semantic`, `POST /keyword`, `GET /cache/stats`, `POST /cache/invalidate` |
| Chat | `api/routes/chat.py` | `POST /chat`, `POST /chat/stream`, `GET /chat/context` |
| Sessions | `api/routes/sessions.py` | `POST/GET /sessions`, `GET/DELETE /{session_id}`, `GET /{session_id}/messages`, `GET /{session_id}/summary` |
| Company Documents | `api/routes/company_documents.py` | `POST /api/company-documents`, `GET /`, `GET /expiring`, `POST /check-expiry`, `GET/PUT/DELETE /{doc_id}` |
| Reminders | `api/routes/reminders.py` | `POST /api/reminders`, `GET /`, `GET /upcoming`, `GET/PUT/DELETE /{reminder_id}` |
| **Inventory** | `api/routes/inventory.py` | `POST /api/inventory/receive`, `POST /api/inventory/issue`, `GET /api/inventory/status`, `GET /api/inventory/{id}/movements` |
| **Sales** | `api/routes/sales.py` | `POST /api/sales/invoices`, `GET /api/sales/invoices`, `GET /api/sales/invoices/{id}` |

Invoice detail (`GET /api/invoices/{id}`) now includes per-item `matched_material_id`, `needs_catalog`, and `catalog_suggestions` (top 5 FTS5 candidates for unmatched line items).

### 1.5 Test Suite

| Area | Count | Status |
|------|-------|--------|
| API tests (catalog, prices, invoices, company-docs, reminders, health, search, sessions, ingest, inventory, sales) | ~54 | All pass |
| Core entity tests (incl. OriginConfidence + ingestion fields + inventory + local sales) | ~85 | All pass |
| Core interface contract tests | ~30 | All pass |
| Infrastructure SQLite store tests (invoice, document, session, material, price history, company-doc, reminder, inventory, sales) | ~168 | All pass |
| Unit service tests (incl. MaterialIngestionService, price anomaly, cross-invoice duplicate) | ~136 | All pass |
| Unit parser tests | ~90 | All pass |
| Unit search tests | ~80 | All pass |
| Unit use case tests (upload, audit, search, chat, proforma, add-to-catalog, auto-match, ingest, check-expiry, receive-stock, issue-stock, create-sales-invoice) | ~85 | All pass |
| Unit scraper tests (AmazonProductFetcher HTML parsing) | ~25 | All pass |
| Integration tests (catalog flow, chat endpoint, inventory flow) | ~13 | All pass |
| **Total** | **916 pass (804 non-API + 112 API), 0 fail** | |

Phase 10 added ~57 new tests: entity (18), store (17), use case (14), API (9), integration (1).
Phase 11 added ~23 new tests: entity (3), service (11), use case (5), API (4).
Phase 12 fixed verify scripts (`cmd /c` for NativeCommandError), ruff I001, and 3 mypy errors.

---

## 2. Gap List

| # | Feature | Current State | Priority |
|---|---------|---------------|----------|
| ~~G1~~ | ~~Materials DB + synonyms~~ | **Done.** `Material` entity, `SQLiteMaterialStore` with FTS5 + synonym management, `IMaterialStore` interface, v005 migration, 16 store tests. | **Done** |
| ~~G2~~ | ~~Add to Catalog flow~~ | **Done.** `AddToCatalogUseCase` — find/create material, add synonyms, link price history, set `matched_material_id`. `POST /api/catalog/`. 7 use case tests + 2 integration tests. Invoice detail shows `needs_catalog` + `catalog_suggestions`. | **Done** |
| ~~G3~~ | ~~Price history application code~~ | **Done.** `IPriceHistoryStore`, `SQLitePriceHistoryStore`, `GET /api/prices/history`, `GET /api/prices/stats`. 9 store tests + 8 API tests. | **Done** |
| ~~G4~~ | ~~Proforma generator~~ | **Done.** `Fpdf2ProformaRenderer`, `POST /api/invoices/{id}/proforma-pdf`, `GenerateProformaPdfUseCase`. | **Done** |
| ~~G5~~ | ~~Company documents + expiry~~ | **Done.** Full CRUD + expiry query. | **Done** |
| ~~G6~~ | ~~Reminders~~ | **Done.** Full CRUD + upcoming query. | **Done** |
| G7 | **Auth / multi-tenant** | `src/srg/core/security.py` has placeholder SHA-256 "tokens" — not JWT, no user model, no RBAC. | **P2 — Medium** |
| G8 | **Web UI completeness** | `main.py` mounts static files + SPA catch-all but no built frontend. | **P2 — Medium** |
| G9 | **Duplicate API surface** | `src/api/` and `src/srg/api/` both define routes. `src/api/` is canonical; `src/srg/api/v1/` is a stale thin wrapper. | **P2 — Medium** |
| G10 | **Currency handling** | `item_price_history` has `currency` column, but no conversion or multi-currency comparison in audit. | **P3 — Low** |
| ~~G11~~ | ~~**Auto-catalog on upload**~~ | **Done.** `auto_match_items()` on `AddToCatalogUseCase` + `AutoMatchResult`. Upload endpoint `auto_catalog=true` by default. Matches by normalized name → synonym fallback. 8 unit tests. | **Done** |
| ~~G12~~ | ~~**Price anomaly audit rule**~~ | **Done.** `_check_price_anomalies()` on `InvoiceAuditorService`. Queries `IPriceHistoryStore`, flags `PRICE_ANOMALY` warning when deviation >20% (configurable). Graceful degradation. 13 unit tests. | **Done** |
| ~~G13~~ | ~~**Cross-invoice duplicate detection**~~ | **Done.** `_check_cross_invoice_duplicates()` on `InvoiceAuditorService`. Queries `IPriceHistoryStore` with configurable window (default 30 days). Flags `CROSS_INVOICE_DUPLICATE` warning. Exact name filtering. Graceful degradation. 12 unit tests. | **Done** |
| ~~G14~~ | ~~**Expiry alert → auto-reminder**~~ | **Done.** `CheckExpiringDocumentsUseCase` + `ExpiryCheckResult`. `IReminderStore.find_by_linked_entity()`. `POST /api/company-documents/check-expiry` endpoint. 8 use case tests + 3 API tests + 1 store test. | **Done** |

---

## 3. Bugs and Warnings

### 3.1 Ruff Lint

**Current: 0 errors.**

### 3.2 Mypy Type Errors

**Current: 0 errors (140 source files)**

Previously 3 errors (list invariance in services.py, missing attr-defined ignores in upload_invoice.py) — fixed in Phase 12 close-out.

### 3.3 Runtime Bugs (low priority)

1. **`health.py:90,204`** — `pool.connection()` may not exist on `ConnectionPool`. Verify correct async context manager method.
2. **`health.py:189`** — `embedder.embed("test")` → should be `embedder.embed_single("test")` per `IEmbeddingProvider`.
3. **`main.py:80`** — `llm.health_check()` → should be `llm.check_health()` per `ILLMProvider`.

### 3.4 Deprecation Warnings

| Warning | Source | Fix |
|---------|--------|-----|
| `datetime.utcnow()` deprecated in Python 3.12 | `document_store.py`, `invoice_store.py`, `session_store.py`, `company_document_store.py`, `reminder_store.py`, `fpdf2_renderer.py`, entity defaults | Replace with `datetime.now(UTC)` |
| ~~`HTTP_422_UNPROCESSABLE_ENTITY` deprecated~~ | ~~`api/middleware/error_handler.py`~~ | **Fixed** in Phase 8 — replaced with literal `422` |

### 3.5 Structural Issues

1. `core/interfaces/parser.py:20`: `ParserResult.items` defaults to `None` but typed as `list[LineItem]`.
2. Dual API surface (`src/api/` vs `src/srg/api/`) — `src/api/` is canonical.

---

## 4. Tooling Status

| Tool | Config | Result |
|------|--------|--------|
| **pytest** | `pyproject.toml` asyncio_mode=auto | 916 pass (804 non-API + 112 API) |
| **ruff** | `pyproject.toml` line-length=100 | 0 errors |
| **mypy** | `pyproject.toml` strict=true | 0 errors (140 files) |
| **coverage** | `pyproject.toml` fail_under=70 | Not measured this run |
| **bandit** | `pyproject.toml` configured | Not run |

### Close-out Tooling

Scripts for milestone close-out (available in both `Scripts/` and `tools/`):
- `verify_all.ps1` — Two-phase tests (non-API then API), lint, type check with PASS/FAIL summary
- `run_all.ps1` — Kill stale uvicorn, run migrations, start server, verify health
- `docs/SMOKE_TEST.md` — Manual verification runbook

### Manual Smoke Test (curl)

After starting the server with `run_all.ps1`:

```bash
# Health check
curl -s http://127.0.0.1:8000/api/health | python -m json.tool

# Upload an invoice
curl -s -X POST http://127.0.0.1:8000/api/invoices/upload \
  -F "file=@sample.pdf" | python -m json.tool

# List invoices
curl -s http://127.0.0.1:8000/api/invoices | python -m json.tool

# List materials catalog
curl -s http://127.0.0.1:8000/api/catalog/ | python -m json.tool

# Price history
curl -s "http://127.0.0.1:8000/api/prices/history?item_name=test" | python -m json.tool

# Company documents
curl -s http://127.0.0.1:8000/api/company-documents | python -m json.tool

# Reminders (upcoming + insights)
curl -s http://127.0.0.1:8000/api/reminders/upcoming | python -m json.tool
curl -s http://127.0.0.1:8000/api/reminders/insights | python -m json.tool

# Inventory status
curl -s http://127.0.0.1:8000/api/inventory/status | python -m json.tool

# Sales invoices
curl -s http://127.0.0.1:8000/api/sales/invoices | python -m json.tool

# Proforma PDF (requires valid invoice_id)
curl -s -X POST http://127.0.0.1:8000/api/invoices/1/proforma-pdf --output proforma.pdf

# Swagger UI — open in browser
# http://127.0.0.1:8000/docs
```

---

## 5. Database Schema

8 applied migrations, 40 tables:

| Migration | Tables / Objects |
|-----------|-----------------|
| v001 | documents, doc_pages, doc_chunks, doc_chunks_fts, doc_chunks_faiss_map, invoices, invoice_items, invoice_items_fts, line_items_faiss_map, chat_sessions, chat_messages, memory_facts, audit_results, indexing_state, schema_migrations |
| v002 | item_price_history + trg_item_price_history trigger + v_item_price_stats view |
| v003 | materials, material_synonyms (original) |
| v004 | company_documents, reminders |
| v005 | materials (TEXT PK), material_synonyms, materials_fts + sync triggers |
| v006 | invoice_items.matched_material_id column + index |
| v007 | materials: source_url, origin_country, origin_confidence, evidence_text, brand columns + indexes |
| v008 | inventory_items, stock_movements, local_sales_invoices, local_sales_items + indexes |

---

## 6. Quick Endpoint Reference

See `docs/FLOW.md` for the full 53-endpoint map.
See `docs/CATALOG_FLOW.md` for the catalog user workflow.
See `docs/INVENTORY_FLOW.md` for the inventory & sales workflow.
See `docs/SMOKE_TEST.md` for manual verification steps.
