# NEXT.md — Checklist for Next 1-2 Development Sessions

**Generated**: 2026-01-27
**Baseline**: 630 tests pass, 84 ruff errors, 365 mypy errors, 3 runtime bugs

---

## Session 1: Stabilize — Fix Bugs + Clean Lint

### Critical Runtime Bugs

- [ ] **Fix `health.py:90,204`** — `pool.connection()` does not exist on ConnectionPool. Verify the correct async context manager method name in `infrastructure/storage/sqlite/connection.py` and fix both occurrences.
- [ ] **Fix `health.py:189`** — `embedder.embed("test")` → should be `embedder.embed_single("test")` (per `IEmbeddingProvider` interface).
- [ ] **Fix `main.py:80`** — `llm.health_check()` → should be `llm.check_health()` (per `ILLMProvider` interface).
- [ ] **Fix `core/interfaces/parser.py:20`** — `ParserResult.items` defaults to `None` but typed as `list[LineItem]`. Change to `items: list[LineItem] = field(default_factory=list)` or make it `Optional[list[LineItem]] = None`.
- [ ] **Fix `core/interfaces/parser.py:24`** — Same pattern: `metadata: dict[str, Any]` defaults to `None`.

### Deprecation Fixes

- [ ] **Replace `datetime.utcnow()`** in `infrastructure/storage/sqlite/document_store.py:83`
- [ ] **Replace `datetime.utcnow()`** in `infrastructure/storage/sqlite/invoice_store.py:164`
- [ ] **Replace `datetime.utcnow()`** in `infrastructure/storage/sqlite/session_store.py:102,229,262`
- [ ] All replacements: `datetime.utcnow()` → `datetime.now(datetime.UTC)`

### Lint Cleanup

- [ ] Run `ruff check --fix src tests` — clears 75 of 84 errors automatically
- [ ] Run `ruff check --fix --unsafe-fixes src tests` — clears remaining 9
- [ ] Verify: `ruff check src tests` returns 0 errors
- [ ] Remove unused `time` import from `api/main.py:191`
- [ ] Remove unused imports from `application/services.py:70-71` (`get_doc_store`, `get_inv_store`)
- [ ] Remove unused imports from `core/services/invoice_auditor.py` (`Any`, `LineItem`, `AuditError`)

### Validation

- [ ] Run `pytest -v` — confirm 630 pass, 0 fail
- [ ] Run `ruff check src tests` — confirm 0 errors
- [ ] Run `mypy src` — note remaining count (expect ~280 down from 365)
- [ ] Confirm no new deprecation warnings added

---

## Session 2: Feature — Materials DB + Price History API

### Materials Entity + Store

- [ ] Create `src/core/entities/material.py`:
  - `Material` (Pydantic): id, name, normalized_name, hs_code, category, unit, description, synonyms (list[str])
  - `MaterialSynonym`: id, material_id, synonym, language
- [ ] Create `src/core/interfaces/material_store.py`:
  - `IMaterialStore(ABC)`: create, get, list, search_by_name, find_by_synonym, add_synonym, remove_synonym
- [ ] Create `src/infrastructure/storage/sqlite/material_store.py`:
  - `SQLiteMaterialStore(IMaterialStore)` — full CRUD
- [ ] Create `src/infrastructure/storage/sqlite/migrations/v003_materials.sql`:
  - `materials` table (id, name, normalized_name, hs_code, category, unit, description, created_at, updated_at)
  - `material_synonyms` table (id, material_id FK, synonym, language, created_at)
  - FTS5 virtual table for material search
  - Indexes on normalized_name, hs_code

### Price History Service

- [ ] Create `src/core/interfaces/price_history.py`:
  - `IPriceHistoryStore(ABC)`: get_price_history(item_name, seller, date_range), get_price_stats(item_name)
- [ ] Create `src/infrastructure/storage/sqlite/price_history_store.py`:
  - Query `item_price_history` table (already exists from v002 migration)
  - Query `v_item_price_stats` view
- [ ] Create API endpoint `GET /api/v1/prices/history?item=...&seller=...`
- [ ] Create API endpoint `GET /api/v1/prices/stats?item=...`

### "Add to Catalog" Use Case

- [ ] Create `src/application/use_cases/add_to_catalog.py`:
  - `AddToCatalogUseCase`: Takes parsed LineItem(s) → creates/updates Material entries
  - Links synonyms from item_name variations
  - Updates price history reference
- [ ] Create API endpoint `POST /api/v1/catalog` (body: list of item IDs from an invoice)
- [ ] Create API endpoint `GET /api/v1/catalog` (list materials with filters)
- [ ] Create API endpoint `GET /api/v1/catalog/{material_id}` (detail with synonyms + price history)

### Tests

- [ ] Unit tests for `Material` entity validation
- [ ] Unit tests for `SQLiteMaterialStore` CRUD
- [ ] Unit tests for `AddToCatalogUseCase`
- [ ] Unit tests for price history queries
- [ ] Integration test: upload invoice → add items to catalog → query catalog

### Validation

- [ ] Run `pytest -v` — all pass including new tests
- [ ] Run `ruff check src tests` — 0 errors
- [ ] Run `mypy src` — no new errors from new code

---

## Quick Reference: File Locations

```
Bug fixes:
  src/api/routes/health.py          (lines 90, 189, 204)
  src/api/main.py                   (line 80)
  src/core/interfaces/parser.py     (lines 20, 24)
  src/infrastructure/storage/sqlite/document_store.py   (line 83)
  src/infrastructure/storage/sqlite/invoice_store.py    (line 164)
  src/infrastructure/storage/sqlite/session_store.py    (lines 102, 229, 262)

New files (Session 2):
  src/core/entities/material.py
  src/core/interfaces/material_store.py
  src/core/interfaces/price_history.py
  src/infrastructure/storage/sqlite/material_store.py
  src/infrastructure/storage/sqlite/price_history_store.py
  src/infrastructure/storage/sqlite/migrations/v003_materials.sql
  src/application/use_cases/add_to_catalog.py
  src/api/routes/catalog.py (or src/srg/api/v1/endpoints/catalog.py)
  tests/core/entities/test_material.py
  tests/infrastructure/storage/sqlite/test_material_store.py
  tests/unit/use_cases/test_add_to_catalog.py
  tests/unit/services/test_price_history.py
```
