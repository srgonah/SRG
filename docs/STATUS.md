# SRG Progress Audit — STATUS.md

**Generated**: 2026-01-27
**Commit scope**: Full `src/`, `tests/`, tooling audit
**Tool results**: pytest 630/630 pass | ruff 84 errors | mypy 365 errors

---

## 1. What Works Now

### 1.1 Core Domain Layer (`src/core/`)

| Feature | Files | Key Classes/Functions | Status |
|---------|-------|----------------------|--------|
| Invoice entity model | `core/entities/invoice.py` | `Invoice`, `LineItem`, `AuditResult`, `AuditIssue`, `ArithmeticCheck` | Complete |
| Document entity model | `core/entities/document.py` | `Document`, `Page`, `Chunk`, `SearchResult`, `IndexingState` | Complete |
| Session/Chat entity model | `core/entities/session.py` | `ChatSession`, `Message`, `MemoryFact` | Complete |
| Exception hierarchy | `core/exceptions.py` | `SRGError` → `StorageError`, `LLMError`, `ParserError`, `SearchError`, `AuditError`, `ChatError`, `IndexingError` | Complete |
| Storage interfaces (ABCs) | `core/interfaces/storage.py` | `IDocumentStore`, `IInvoiceStore`, `ISessionStore`, `IVectorStore`, `IHybridSearcher`, `IReranker`, `ISearchCache` | Complete |
| LLM interfaces | `core/interfaces/llm.py` | `ILLMProvider`, `IVisionProvider`, `IEmbeddingProvider` | Complete |
| Parser interfaces | `core/interfaces/parser.py` | `IInvoiceParser`, `ITemplateDetector`, `ITextExtractor`, `IParserRegistry` | Complete |
| Chat service | `core/services/chat_service.py` | `ChatService.create_session()`, `.send_message()`, `.stream_response()`, `.extract_memory_facts()` | Complete |
| Search service | `core/services/search_service.py` | `SearchService.search()`, `.search_items()`, `.prepare_context()` | Complete |
| Invoice parser service | `core/services/invoice_parser.py` | `InvoiceParserService.parse_invoice()`, `.parse_page()` | Complete |
| Invoice auditor service | `core/services/invoice_auditor.py` | `InvoiceAuditorService.audit_invoice()`, `_check_math()`, `_check_required_fields()`, `_check_bank_details()`, `_check_format()`, `_llm_semantic_analysis()` | Complete |
| Document indexer service | `core/services/document_indexer.py` | `DocumentIndexerService.index_document()`, `.index_incremental()`, `.rebuild_index_full()` | Complete |

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
| FAISS vector store (chunks + items indexes) | `infrastructure/storage/vector/faiss_store.py` | Complete |
| SQLite FTS5 keyword search | `infrastructure/search/fts.py` | Complete |
| Hybrid searcher (FAISS + FTS + RRF) | `infrastructure/search/hybrid.py` | Complete |
| Reranker (BGE-reranker-v2-m3) | `infrastructure/search/reranker.py` | Complete |
| Database migrations v001 (initial schema) | `migrations/v001_initial_schema.sql` | Complete |
| Database migrations v002 (price history) | `migrations/v002_price_history.sql` | Schema only — no application code reads it |
| Memory + disk caching | `infrastructure/cache/memory_cache.py`, `disk_cache.py` | Complete |

### 1.3 Application Layer (`src/application/`)

| Use Case | File | Status |
|----------|------|--------|
| Upload Invoice | `application/use_cases/upload_invoice.py` | Complete |
| Audit Invoice | `application/use_cases/audit_invoice.py` | Complete |
| Search Documents | `application/use_cases/search_documents.py` | Complete |
| Chat With Context (RAG) | `application/use_cases/chat_with_context.py` | Complete |
| DTOs (request/response) | `application/dto/requests.py`, `responses.py` | Complete |
| Service factory (singletons) | `application/services.py` | Has unused imports (see bugs) |

### 1.4 API Layer — Two Parallel API Surfaces

#### Primary API (`src/api/`)
| Router | File | Endpoints |
|--------|------|-----------|
| Health | `api/routes/health.py` | `GET /health/ready`, `/health/live` |
| Invoices | `api/routes/invoices.py` | `POST /invoices/upload`, `GET/PUT/DELETE /invoices/{id}`, `GET /invoices` |
| Documents | `api/routes/documents.py` | `GET /documents`, `GET /documents/{id}`, `DELETE` |
| Search | `api/routes/search.py` | `POST /search` |
| Chat | `api/routes/chat.py` | `POST /chat`, `POST /chat/stream` |
| Sessions | `api/routes/sessions.py` | `POST/GET/PUT/DELETE /sessions` |

#### Secondary API (`src/srg/api/v1/endpoints/`)
Thin wrapper reusing same use cases, adds `/api/v1/` prefix, placeholder auth, separate Pydantic schemas.

### 1.5 Test Suite

| Area | Count | Status |
|------|-------|--------|
| API tests | ~15 | All pass |
| Core entity tests | ~50 | All pass |
| Core interface contract tests | ~30 | All pass |
| Infrastructure SQLite store tests | ~120 | All pass |
| Unit service tests | ~100 | All pass |
| Unit parser tests | ~90 | All pass |
| Unit search tests | ~80 | All pass |
| Unit use case tests | ~40 | All pass |
| Integration tests | ~10 | All pass |
| **Total** | **630** | **630 pass, 0 fail** |

---

## 2. What Is Missing (GAP LIST)

Features requested in the product spec vs. current implementation:

| # | Feature | Current State | Priority |
|---|---------|---------------|----------|
| G1 | **Materials DB + synonyms** | No `materials` table, no synonym mapping, no entity for materials. Only `item_price_history` exists at DB level. | **P0 — Critical** |
| G2 | **"Add to catalog" flow** | No catalog entity, no API endpoint, no use case. Users cannot save parsed line items as catalog entries. | **P0 — Critical** |
| G3 | **Proforma generator** | `AuditResult.proforma_summary` field exists (dict, stored as JSON) but there is no proforma *document generation* — no PDF output, no template engine, no use case. | **P1 — High** |
| G4 | **Company documents + expiry reminders** | `Document` has `company_key` field. No `CompanyDocument` entity with expiry dates. No reminder/notification system. No cron/scheduler. | **P1 — High** |
| G5 | **Price history application code** | `v002_price_history.sql` creates the table + trigger + view, but no `IPriceHistoryStore` interface, no service, no API endpoint to query price trends. | **P1 — High** |
| G6 | **Auth / multi-tenant** | `src/srg/core/security.py` has placeholder SHA-256 "tokens" — not JWT, no user model, no RBAC. | **P2 — Medium** |
| G7 | **PDF export / report generation** | No PDF output anywhere. PyMuPDF used only for reading. | **P2 — Medium** |
| G8 | **Web UI completeness** | `main.py` mounts static files + SPA catch-all but no evidence of a built frontend. | **P2 — Medium** |
| G9 | **Duplicate API surface** | `src/api/` and `src/srg/api/` both define routes for the same features. Needs consolidation. | **P2 — Medium** |
| G10 | **Currency handling** | `item_price_history` has `currency` column, but no currency conversion, no multi-currency comparison in audit. | **P3 — Low** |

---

## 3. Bugs Found

### 3.1 Ruff Lint (84 errors, all auto-fixable)

| Category | Count | Key Files |
|----------|-------|-----------|
| **F401** Unused imports | ~60 | `application/services.py` (unused `get_document_store`, `get_invoice_store`), `core/services/invoice_auditor.py` (unused `Any`, `LineItem`, `AuditError`), `core/services/chat_service.py` (unused `SearchContext`), many test files |
| **I001** Unsorted imports | ~15 | `application/services.py`, `infrastructure/parsers/__init__.py`, several test files |
| **F841** Assigned but unused variables | 2 | `tests/unit/services/test_document_indexer_incremental.py:260`, `tests/unit/use_cases/test_chat_with_context_uc.py:164` |

**Fix**: `ruff check --fix src tests` resolves 75 of 84; remaining 9 need `--unsafe-fixes`.

### 3.2 Mypy Type Errors (365 errors in 60 files)

| Category | Count | Impact |
|----------|-------|--------|
| `[type-arg]` Missing generic params (`dict` → `dict[str, Any]`) | ~80 | Cosmetic, strict mode |
| `[no-untyped-def]` Missing return/param annotations | ~120 | Mostly API routes + factory functions |
| `[assignment]` Incompatible types (e.g. `None` assigned to `list[LineItem]`) | ~20 | `core/interfaces/parser.py:20,24` — real bugs in dataclass defaults |
| `[attr-defined]` Wrong attribute names | 4 | **Real bugs**: `health.py:90,204` uses `pool.connection()` (should be `pool._connections` or async context), `health.py:189` calls `embedder.embed()` (should be `embed_single()`), `main.py:80` calls `llm.health_check()` (interface has `check_health()`) |
| `[arg-type]` Wrong argument types | ~15 | `documents.py:48` passes `str | None` to `Path()` |
| `[misc]` List comprehension type mismatches | ~10 | `invoices.py:231` — dict vs AuditFindingResponse |

### 3.3 Runtime Bugs (from mypy attr-defined)

These will crash at runtime if hit:

1. **`src/api/routes/health.py:90,204`** — `pool.connection()` does not exist on `ConnectionPool`. The correct API depends on the pool implementation.
2. **`src/api/routes/health.py:189`** — `embedder.embed("test")` — interface defines `embed_single()`, not `embed()`.
3. **`src/api/main.py:80`** — `llm.health_check()` — interface defines `check_health()`, not `health_check()`.

### 3.4 Deprecation Warnings (698 in test run)

| Warning | Files | Fix |
|---------|-------|-----|
| `datetime.utcnow()` deprecated in Python 3.12 | `document_store.py:83`, `invoice_store.py:164`, `session_store.py:102,229,262` | Replace with `datetime.now(UTC)` |
| aiosqlite default date adapter deprecated | `test_invoice_store.py` (15 occurrences) | Register custom adapter |

### 3.5 Structural Issues

1. **Unused imports in `application/services.py:70-71`**: `get_document_store` and `get_invoice_store` imported but never used — factory function may be incomplete.
2. **Unused `time` import in `api/main.py:191`**: Dead code in `root_health()`.
3. **`core/interfaces/parser.py:20`**: `ParserResult.items` defaults to `None` but is typed as `list[LineItem]` — will fail at runtime if accessed before set.

---

## 4. Tooling Status

| Tool | Config | Result |
|------|--------|--------|
| **pytest** | `pyproject.toml` `[tool.pytest.ini_options]` asyncio_mode=auto | 630/630 pass (22s) |
| **ruff** | `pyproject.toml` `[tool.ruff]` line-length=100, py311 | 84 errors (all fixable) |
| **mypy** | `pyproject.toml` `[tool.mypy]` strict=true | 365 errors in 60 files |
| **coverage** | `pyproject.toml` `[tool.coverage]` fail_under=70 | Not measured this run |
| **bandit** | `pyproject.toml` `[tool.bandit]` configured | Not run |
| **commitizen** | `pyproject.toml` `[tool.commitizen]` | Configured |

---

## 5. Next Steps (Top 15, Prioritized)

| # | Task | Priority | Depends On | Files to Create/Modify |
|---|------|----------|------------|----------------------|
| 1 | **Fix 3 runtime bugs** (wrong method names in health.py, main.py) | P0 | — | `api/routes/health.py`, `api/main.py` |
| 2 | **Fix `ParserResult.items` default** (`None` → `[]` or `Optional[list]`) | P0 | — | `core/interfaces/parser.py` |
| 3 | **Run `ruff check --fix`** to clear 84 lint errors | P0 | — | Multiple files |
| 4 | **Replace `datetime.utcnow()`** with `datetime.now(UTC)` across stores | P0 | — | 3 store files |
| 5 | **Materials DB entity + store** — `Material` entity, `IMaterialStore`, SQLite impl, migration v003 | P1 | — | New: `core/entities/material.py`, `core/interfaces/material_store.py`, `infrastructure/storage/sqlite/material_store.py`, `migrations/v003_materials.sql` |
| 6 | **Material synonyms** — synonym table, fuzzy matching, link to line items | P1 | #5 | Extend migration v003, new `MaterialSynonymService` |
| 7 | **"Add to catalog" use case** — save parsed items as catalog entries | P1 | #5 | New: `application/use_cases/add_to_catalog.py`, API route |
| 8 | **Price history service** — query `item_price_history`, expose via API | P1 | — | New: `core/interfaces/price_history.py`, `infrastructure/storage/sqlite/price_history_store.py`, API route |
| 9 | **Proforma generator** — generate proforma PDF from invoice + audit data | P1 | — | New: `core/services/proforma_generator.py`, PDF template, API route |
| 10 | **Company documents + expiry** — `CompanyDocument` entity with expiry dates, reminder query | P1 | — | New entity, store, migration v004, API endpoints |
| 11 | **Consolidate dual API surfaces** — merge `src/srg/api/` into `src/api/` or vice versa | P2 | — | Refactor across both API layers |
| 12 | **Add type annotations** to API routes to satisfy mypy strict | P2 | #3 | All files in `api/routes/` |
| 13 | **Fix mypy dict generic params** across entities/DTOs | P2 | — | ~20 files in core/entities, application/dto |
| 14 | **Implement proper JWT auth** replacing placeholder SHA-256 tokens | P2 | #11 | `core/security.py`, middleware |
| 15 | **Run coverage report** and bring to ≥80% (current threshold: 70%) | P3 | — | Test files |
