# NEXT.md — Checklist for Next Development Session

**Updated**: 2026-01-28
**Baseline**: ~891 tests pass | ruff 0 errors | mypy 0 errors

---

## Session 1: Stabilize — COMPLETE

> Previous baseline: 630 tests, 84 ruff errors, 365 mypy errors.
> Final: 674 tests, 0 ruff errors, 0 mypy errors.

All stabilization tasks completed. See STATUS.md Section 3 for remaining low-priority runtime bugs and deprecation warnings.

---

## Session 2: Feature — Materials DB + Synonyms + Add to Catalog + Price History — COMPLETE

> All tasks completed across Milestone Days 1-7.

### Completed

- [x] **Materials catalog** — `Material` entity, `IMaterialStore` (9 methods), `SQLiteMaterialStore` with FTS5 + synonym management, v005 migration, 16 store tests
- [x] **Synonym fuzzy matching** — `search_by_name()` uses FTS5 MATCH across `materials_fts`, `add_synonym()`, `remove_synonym()`, `list_synonyms()` all implemented
- [x] **Add to Catalog use case** — `AddToCatalogUseCase`: find/create material, add synonyms, link price history, set `matched_material_id`. 7 unit tests + 2 integration tests
- [x] **Price history service** — `IPriceHistoryStore`, `SQLitePriceHistoryStore` (queries `item_price_history` + `v_item_price_stats`). 9 store tests + 8 API tests
- [x] **Catalog API** — `POST /api/catalog/`, `GET /api/catalog/`, `GET /api/catalog/{material_id}`. 7 API tests
- [x] **Price API** — `GET /api/prices/history`, `GET /api/prices/stats`. 8 API tests
- [x] **Invoice detail catalog fields** — `matched_material_id`, `needs_catalog`, `catalog_suggestions` (top 5 FTS5 candidates). 4 tests
- [x] **v005 migration** — `materials` (TEXT PK), `material_synonyms`, `materials_fts` + sync triggers
- [x] **v006 migration** — `invoice_items.matched_material_id` column + index
- [x] **Documentation** — `CATALOG_FLOW.md`, updated `STATUS.md`
- [x] **Validation** — pytest 734/738 pass, ruff 0 errors, mypy 0 errors (118 files)

---

## Phase 8: Product Hardening & Reliability — COMPLETE

### Completed

- [x] **Standardized error responses** — `ErrorResponse` now has `error_code`, `message`, `hint` fields; error handler extracts `SRGError.code` for machine-readable codes; `_infer_error_code()` maps HTTPException details to codes
- [x] **Fixed 4 known test failures** — company docs + reminders API tests used `@patch` instead of `app.dependency_overrides`; now all 738/738 pass
- [x] **Fixed HTTP_422 deprecation** — replaced `HTTP_422_UNPROCESSABLE_ENTITY` with literal `422` in error handler and routes
- [x] **Updated invoice test assertions** — error field changed from `error` to `message`
- [x] **Defined 3 smoke test scenarios** — clean invoice, math errors, add-to-catalog flow
- [x] **DB schema freeze confirmed** — v001-v006 documented and frozen, next is v007
- [x] **Created docs/HARDENING.md** — known limits, safe usage rules, recovery steps, error code reference

---

## Phase 9: External Material Intelligence (Amazon Ingestion) — COMPLETE

### Completed

- [x] **v007 migration** — Added `source_url`, `origin_country`, `origin_confidence`, `evidence_text`, `brand` columns to `materials` table + indexes
- [x] **Material entity updated** — `OriginConfidence` enum (confirmed/likely/unknown), new fields: `brand`, `source_url`, `origin_country`, `origin_confidence`, `evidence_text`
- [x] **IProductPageFetcher interface** — Abstract interface for e-commerce page fetching (`ProductPageData`, `fetch()`, `supports_url()`)
- [x] **MaterialIngestionService** — Core service orchestrating URL fetch → normalize → deduplicate → create/update material + synonyms
- [x] **AmazonProductFetcher** — Supports amazon.ae/com/co.uk/de/fr/sa; multi-layer extraction: JSON-LD → HTML elements → regex; origin detection from detail table + text patterns
- [x] **IngestMaterialUseCase** — Application use case wrapping ingestion service
- [x] **DTOs** — `IngestMaterialRequest` (url, category, unit), `IngestMaterialResponse` (material, created, synonyms_added, origin info)
- [x] **API endpoint** — `POST /api/catalog/ingest` → 201 Created with full ingestion response
- [x] **Updated existing catalog endpoints** — `list_materials` and `get_material` now return brand/source_url/origin_country/origin_confidence
- [x] **SQLiteMaterialStore updated** — CREATE/UPDATE/READ include all new columns; backward-compatible `_row_to_material`
- [x] **Service factory** — `get_material_ingestion_service()` wires AmazonProductFetcher + SQLiteMaterialStore
- [x] **52 new tests** — entity (7), ingestion service (11), amazon fetcher (25), use case (3), API (6)
- [x] **All test fixtures updated** — conftest.py, test_material_store.py, test_catalog_flow.py schemas include new columns
- [x] **Documentation** — STATUS.md and NEXT.md updated
- [x] **Validation** — pytest 790/790 pass, 0 fail

---

## Session 3: Next Features

### 3.1 Auto-Catalog on Upload (G11 — P1 High) — COMPLETE

- [x] Added `auto_match_items()` method + `AutoMatchResult` dataclass to `AddToCatalogUseCase`
- [x] On upload, for each LINE_ITEM: search by normalized name → synonym fallback → set `matched_material_id` + link price history
- [x] Added `auto_catalog` flag to upload endpoint (default `true`) and `UploadInvoiceRequest` DTO
- [x] `UploadInvoiceUseCase.execute()` calls auto-match after audit, returns catalog stats in response
- [x] 8 unit tests: match by name, match by synonym, unmatched, mixed, skip non-line-items, skip empty names, invoice not found, no material creation

### 3.2 Price Anomaly Audit Rule (G12 — P1 High) — COMPLETE

- [x] Added `_check_price_anomalies()` async method to `InvoiceAuditorService`
- [x] Queries `IPriceHistoryStore.get_price_stats()` — item+seller first, item-only fallback
- [x] Creates `AuditIssue(code="PRICE_ANOMALY", severity=WARNING)` when deviation > threshold
- [x] Configurable threshold (default 20%) via constructor param `price_anomaly_threshold`
- [x] Requires ≥2 historical records + positive avg_price before flagging
- [x] Graceful degradation: no price store → skip; DB error → INFO issue
- [x] Service factory (`get_invoice_auditor_service()`) wires `SQLitePriceHistoryStore` automatically
- [x] 13 unit tests: no store, no stats, within/above/below threshold, custom threshold, skip non-line-items, skip zero price, insufficient history, multiple items, full audit integration, error degradation

### 3.3 Cross-Invoice Duplicate Detection (G13 — P2 Medium) — COMPLETE

- [x] Added `_check_cross_invoice_duplicates()` async method to `InvoiceAuditorService`
- [x] Queries `IPriceHistoryStore.get_price_history()` with configurable date window (default 30 days)
- [x] For each LINE_ITEM: compute window (invoice_date - N days to invoice_date - 1 day), query history, filter exact normalized name matches
- [x] Creates `AuditIssue(code="CROSS_INVOICE_DUPLICATE", severity=WARNING)` with dates info
- [x] Graceful degradation: no price store → skip; no invoice_date → skip; DB error → INFO issue
- [x] Configurable via `duplicate_window_days` constructor param
- [x] 12 unit tests: no store, no date, no history, duplicate found, no seller, skip non-line-items, skip empty names, custom window, inexact filtering, multiple items mixed, full audit integration, error degradation

### 3.4 Expiry Alert → Auto-Reminder (G14 — P2 Medium) — COMPLETE

- [x] Added `find_by_linked_entity()` abstract method to `IReminderStore` interface
- [x] Implemented `find_by_linked_entity()` in `SQLiteReminderStore` with SQL filter on `linked_entity_type` + `linked_entity_id`
- [x] Created `CheckExpiringDocumentsUseCase` with `ExpiryCheckResult` dataclass
- [x] Use case: lists expiring docs → checks for active (not done) reminders → creates new reminder with title/message/due_date
- [x] Added `POST /api/company-documents/check-expiry` endpoint with `within_days` query param
- [x] Added `ExpiryCheckResponse` DTO and `get_check_expiring_documents_use_case()` dependency
- [x] 8 use case tests: no expiring docs, creates reminder, skips already reminded, creates when existing done, multiple mixed, skips no-id docs, custom within_days, reminder message content
- [x] 3 API tests: endpoint exists, returns result, custom window
- [x] 1 store-level test: `find_by_linked_entity` query correctness

---

## Phase 10: Inventory & Local Sales System — COMPLETE

### Completed

- [x] **Inventory entities** — `InventoryItem` (WAC + total_value), `StockMovement` (IN/OUT/ADJUST), `MovementType` enum
- [x] **Local sales entities** — `LocalSalesInvoice` (auto-computed totals/profit), `LocalSalesItem` (line_total, cost_basis, profit)
- [x] **Core exceptions** — `InventoryError`, `InsufficientStockError`, `InventoryItemNotFoundError`, `SalesError`, `SalesInvoiceNotFoundError`
- [x] **Core interfaces** — `IInventoryStore` (7 methods), `ISalesStore` (3 methods)
- [x] **v008 migration** — `inventory_items`, `stock_movements`, `local_sales_invoices`, `local_sales_items` tables with indexes and FKs
- [x] **SQLiteInventoryStore** — CRUD + movement tracking with `get_connection()` / `get_transaction()`
- [x] **SQLiteSalesStore** — Invoice creation with items in single transaction, JOIN-based retrieval
- [x] **Application DTOs** — `ReceiveStockRequest/Response`, `IssueStockRequest/Response`, `CreateSalesInvoiceRequest/Response`, `InventoryStatusResponse`, `SalesInvoiceListResponse`
- [x] **ReceiveStockUseCase** — WAC recalculation, create-or-update inventory item, record IN movement
- [x] **IssueStockUseCase** — Balance check, deduct stock, record OUT movement at current avg_cost
- [x] **CreateSalesInvoiceUseCase** — Multi-item stock deduction, cost basis computation, profit calculation
- [x] **Inventory API** — `POST /receive`, `POST /issue`, `GET /status`, `GET /{id}/movements`
- [x] **Sales API** — `POST /invoices`, `GET /invoices`, `GET /invoices/{id}`
- [x] **~57 new tests** — entity (18), store (17), use case (14), API (9), integration (1)
- [x] **Documentation** — `INVENTORY_FLOW.md` (entities, WAC formula, stock flow, API endpoints, error codes)

---

### 3.5 API Surface Cleanup (G9 — P2 Medium)

- [ ] Consolidate `src/api/` (canonical) and `src/srg/api/v1/` (stale wrapper)
- [ ] Remove or redirect `src/srg/api/v1/` routes to canonical `src/api/` routes
- [ ] Update any imports referencing the stale surface

### 3.6 Auth / Multi-Tenant (G7 — P2 Medium)

- [ ] Replace placeholder SHA-256 tokens in `src/srg/core/security.py` with JWT
- [ ] Add user model and RBAC middleware
- [ ] Scope data by tenant/user

---

## Session 3 Validation

```bash
pytest -v
ruff check src tests
mypy src
```

---

## Low-Priority Bugs (carried from Session 1)

- [ ] `health.py:90,204` — `pool.connection()` may not exist on ConnectionPool
- [ ] `health.py:189` — `embedder.embed("test")` → should be `embedder.embed_single("test")`
- [ ] `main.py:80` — `llm.health_check()` → should be `llm.check_health()`
- [ ] `core/interfaces/parser.py:20` — `ParserResult.items` defaults to `None` but typed as `list[LineItem]`
- [ ] Replace `datetime.utcnow()` → `datetime.now(UTC)` in all stores and entity defaults
- [x] ~~Replace `HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT` in error handler~~ — Fixed in Phase 8

---

## Migration Numbering Note

Applied migrations (v001–v006):
- `v001_initial_schema.sql` — core tables (documents, invoices, sessions, etc.)
- `v002_price_history.sql` — `item_price_history` table + trigger + stats view
- `v003_materials.sql` — `materials` + `material_synonyms` tables (original)
- `v004_company_docs_reminders.sql` — `company_documents` + `reminders` tables
- `v005_materials_catalog.sql` — `materials` (TEXT PK), `material_synonyms`, `materials_fts` + sync triggers
- `v006_matched_material_id.sql` — `invoice_items.matched_material_id` column + FK index
- `v007_material_ingestion.sql` — `materials` ingestion columns (source_url, origin_country, origin_confidence, evidence_text, brand) + indexes

- `v008_inventory_sales.sql` — `inventory_items`, `stock_movements`, `local_sales_invoices`, `local_sales_items` tables + indexes

**Next available migration number is v009.**
