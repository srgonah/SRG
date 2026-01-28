# HARDENING.md — Product Reliability Guide

**Updated**: 2026-01-28
**Baseline**: 738 tests pass (738 collected, 0 fail) | ruff 0 errors | mypy 0 errors (118 files)

---

## 1. Smoke Test Scenarios

Three real-world scenarios to verify the system end-to-end.

### Scenario A: Clean Invoice (Happy Path)

**Goal**: Upload a valid invoice where all items match existing catalog materials.

```bash
# 1. Start server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# 2. Health check
curl -s http://127.0.0.1:8000/api/health | python -m json.tool
# Expected: {"status": "ok", ...}

# 3. Upload a clean invoice
curl -X POST http://127.0.0.1:8000/api/invoices/upload \
  -F "file=@test_invoice.pdf" \
  -F "auto_audit=true"
# Expected: 201 with invoice_id, document_id, confidence > 0.5

# 4. Verify invoice detail
curl -s http://127.0.0.1:8000/api/invoices/{invoice_id} | python -m json.tool
# Expected: line_items with needs_catalog=false (if materials exist)

# 5. Verify audit result
curl -s http://127.0.0.1:8000/api/invoices/{invoice_id}/audits | python -m json.tool
# Expected: array with at least one audit, error_count=0

# 6. Check price history
curl -s "http://127.0.0.1:8000/api/prices/stats" | python -m json.tool
# Expected: stats array with entries for the uploaded items
```

**Pass criteria**: All responses return 200/201 with valid JSON, no error_count in audit.

### Scenario B: Invoice with Math + Bank Errors

**Goal**: Upload an invoice with known arithmetic errors and missing bank details.

```bash
# 1. Upload an invoice with errors (quantity * unit_price != total_price)
curl -X POST http://127.0.0.1:8000/api/invoices/upload \
  -F "file=@bad_math_invoice.pdf" \
  -F "auto_audit=true"
# Expected: 201 with audit attached

# 2. Check audit findings
curl -s http://127.0.0.1:8000/api/invoices/{invoice_id}/audits | python -m json.tool
# Expected: findings array with:
#   - code: "MATH_ERROR", severity: "error"
#   - code: "MISSING_BANK_DETAILS", severity: "warning" (if applicable)

# 3. Verify error response for non-existent invoice
curl -s http://127.0.0.1:8000/api/invoices/999999 -w "\nHTTP %{http_code}\n"
# Expected: HTTP 404 with standardized error:
# {
#   "error_code": "INVOICE_NOT_FOUND",
#   "message": "Invoice not found: 999999",
#   "hint": "Check the invoice ID and try GET /api/invoices to list available invoices."
# }

# 4. Verify validation error
curl -X POST http://127.0.0.1:8000/api/invoices/upload \
  -F "file=@test.txt" \
  -w "\nHTTP %{http_code}\n"
# Expected: HTTP 400 with error_code: "BAD_REQUEST"
```

**Pass criteria**: Audit catches math errors; error responses include error_code, message, hint.

### Scenario C: Invoice with New Items Requiring Catalog

**Goal**: Upload an invoice with unknown items, then add them to the catalog.

```bash
# 1. Upload an invoice with items not in the catalog
curl -X POST http://127.0.0.1:8000/api/invoices/upload \
  -F "file=@new_items_invoice.pdf" \
  -F "auto_audit=true"
# Save invoice_id

# 2. Check invoice detail — items should need catalog
curl -s http://127.0.0.1:8000/api/invoices/{invoice_id} | python -m json.tool
# Expected: line_items with needs_catalog=true, catalog_suggestions may be []

# 3. Add items to catalog
curl -X POST http://127.0.0.1:8000/api/catalog/ \
  -H "Content-Type: application/json" \
  -d '{"invoice_id": {invoice_id}}'
# Expected: 200 with materials_created > 0

# 4. Re-check invoice detail — items should now be matched
curl -s http://127.0.0.1:8000/api/invoices/{invoice_id} | python -m json.tool
# Expected: line_items with needs_catalog=false, matched_material_id set

# 5. Browse catalog
curl -s http://127.0.0.1:8000/api/catalog/ | python -m json.tool
# Expected: materials array with newly created entries

# 6. Check price stats
curl -s "http://127.0.0.1:8000/api/prices/stats" | python -m json.tool
# Expected: stats for the newly cataloged items
```

**Pass criteria**: Items flow from needs_catalog=true to matched; catalog and price stats are populated.

---

## 2. Standardized Error Response Format

All API error responses follow this structure:

```json
{
  "error_code": "INVOICE_NOT_FOUND",
  "message": "Invoice not found: 42",
  "hint": "Check the invoice ID and try GET /api/invoices to list available invoices.",
  "detail": null,
  "path": "/api/invoices/42",
  "timestamp": "2026-01-28T00:00:00.000000"
}
```

### Error Code Reference

| error_code | HTTP Status | When |
|------------|-------------|------|
| `INVOICE_NOT_FOUND` | 404 | Invoice ID does not exist |
| `DOCUMENT_NOT_FOUND` | 404 | Document ID does not exist |
| `SESSION_NOT_FOUND` | 404 | Chat session ID does not exist |
| `MATERIAL_NOT_FOUND` | 404 | Material ID does not exist |
| `COMPANY_DOCUMENT_NOT_FOUND` | 404 | Company document ID does not exist |
| `REMINDER_NOT_FOUND` | 404 | Reminder ID does not exist |
| `NOT_FOUND` | 404 | Generic not-found |
| `BAD_REQUEST` | 400 | Invalid parameters |
| `VALIDATION_ERROR` | 400/422 | Pydantic or input validation failure |
| `UNPROCESSABLE_ENTITY` | 422 | Valid syntax but unprocessable content |
| `PARSING_FAILED` | 422 | Invoice PDF could not be parsed |
| `TEMPLATE_NOT_FOUND` | 422 | No parser template for this company |
| `EXTRACTION_ERROR` | 422 | Text extraction from file failed |
| `DUPLICATE_DOCUMENT` | 500 | File hash already exists |
| `DATABASE_ERROR` | 500 | SQLite operation failed |
| `AUDIT_FAILED` | 500 | Audit could not complete |
| `LLM_UNAVAILABLE` | 503 | Ollama / llama.cpp provider down |
| `LLM_TIMEOUT` | 503 | LLM request timed out |
| `CIRCUIT_BREAKER_OPEN` | 503 | Too many LLM failures, in cooldown |
| `INDEX_NOT_READY` | 500 | FAISS index not built |
| `EMBEDDING_ERROR` | 500 | Embedding generation failed |

### Hint Messages

Every error code maps to a hint suggesting how to recover. Hints are pre-defined in `src/api/middleware/error_handler.py:HINT_MAP`.

---

## 3. Database Schema Freeze

The schema is stable at **v006** with 6 applied migrations. All tables are in production use.

### Applied Migrations

| Version | Name | Tables / Objects | Status |
|---------|------|-----------------|--------|
| v001 | initial_schema | documents, doc_pages, doc_chunks, doc_chunks_fts, doc_chunks_faiss_map, invoices, invoice_items, invoice_items_fts, line_items_faiss_map, chat_sessions, chat_messages, memory_facts, audit_results, company_templates, indexing_state, schema_migrations + views + triggers | Frozen |
| v002 | price_history | item_price_history, trg_item_price_history, v_item_price_stats | Frozen |
| v003 | materials (original) | Superseded by v005 | Frozen (replaced) |
| v004 | company_docs_reminders | company_documents, reminders | Frozen |
| v005 | materials_catalog | materials (TEXT PK), material_synonyms, materials_fts + sync triggers | Frozen |
| v006 | matched_material_id | invoice_items.matched_material_id + index | Frozen |

**Next available migration number**: v007

### Schema Integrity Checks

- All foreign keys use `ON DELETE CASCADE` or `ON DELETE SET NULL` as appropriate
- FTS5 sync triggers exist for: `doc_chunks`, `invoice_items`, `materials`
- Auto-`updated_at` triggers exist for: `documents`, `invoices`, `chat_sessions`, `memory_facts`
- Price history auto-populated via `trg_item_price_history` trigger on `invoice_items` INSERT

### Safe Schema Rules

1. **Never modify existing migrations** — they are immutable once applied
2. **New changes go into v007+** — use `ALTER TABLE ADD COLUMN` for additive changes
3. **FTS5 content sync** — any table with FTS5 must have INSERT/UPDATE/DELETE triggers
4. **TEXT PKs for materials** — materials and material_synonyms use UUID TEXT PKs; everything else uses INTEGER AUTOINCREMENT
5. **Test migrations on fresh DB** — run `python -m src.infrastructure.storage.sqlite.migrations.migrator` on a blank database before deploying

---

## 4. Known Limits

### 4.1 Concurrency

- SQLite WAL mode supports concurrent reads but serializes writes
- FAISS index is in-memory and not thread-safe for concurrent writes (rebuild is single-threaded)
- The circuit breaker is per-process; multiple workers don't share state

### 4.2 File Size

- No hard upload size limit enforced by the server (add `--limit-request-body` to uvicorn if needed)
- Large PDFs (>50 pages) may slow parsing significantly
- The `FileTooLargeError` exception exists but is not wired to a configurable limit

### 4.3 LLM Dependency

- Audit LLM analysis is optional (`use_llm=false` to skip)
- Chat requires a running LLM provider (Ollama or llama.cpp)
- If the LLM provider is down, circuit breaker opens after repeated failures
- Semantic search requires embedding provider (BGE-M3)

### 4.4 Data Integrity

- No multi-tenant isolation — all data is in one SQLite database
- No authentication — all endpoints are open (placeholder in `src/srg/core/security.py`)
- No backup strategy beyond SQLite WAL journal files

### 4.5 FTS5 Limitations

- FTS5 MATCH can fail on very short queries (1-2 chars) or special characters
- Material catalog suggestions silently catch FTS5 errors (by design)
- Synonym search only matches exact `normalized_name` or synonym text, not fuzzy

### 4.6 Price History

- Price history is append-only (no edits/deletes)
- Stats view (`v_item_price_stats`) groups by `item_name_normalized + hs_code + seller_name + currency`
- No currency conversion — comparing prices across currencies will give incorrect results

---

## 5. Safe Usage Rules

### 5.1 Development

```bash
# Always run the full suite before deploying
pytest -v
ruff check src tests
mypy src
```

### 5.2 Database Operations

- **Always back up** `srg.db` before running migrations
- **Never delete** `schema_migrations` rows — the migrator uses them to track applied versions
- Use `python -m src.infrastructure.storage.sqlite.migrations.migrator` for migrations — never run SQL files manually in a different order

### 5.3 API Usage

- Use the paginated endpoints (`limit`, `offset`) for large result sets
- Call `GET /api/health` before heavy operations to verify provider availability
- For invoice upload, always check the response `confidence` score — low confidence means parsing may be incomplete

### 5.4 Catalog Operations

- Run `POST /api/catalog/` after upload to link items to materials
- The catalog deduplicates by `normalized_name` — uploading the same item twice won't create duplicates
- Synonyms are additive — removing synonyms requires direct database access

---

## 6. Recovery Steps

### 6.1 Server Won't Start

```bash
# Check Python version (requires 3.12+)
python --version

# Reinstall dependencies
pip install -e ".[dev]"

# Check for port conflicts
netstat -an | findstr 8000

# Start with verbose logging
uvicorn src.api.main:app --log-level debug
```

### 6.2 Database Corrupted

```bash
# Check integrity
sqlite3 srg.db "PRAGMA integrity_check;"

# If corrupted, restore from backup
cp srg.db.bak srg.db

# Re-run migrations (safe — uses INSERT OR IGNORE)
python -m src.infrastructure.storage.sqlite.migrations.migrator
```

### 6.3 LLM Provider Down

```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Restart Ollama
# (Linux) systemctl restart ollama
# (Windows) Restart Ollama app

# Test without LLM
curl -X POST "http://127.0.0.1:8000/api/invoices/{id}/audit?use_llm=false"
```

### 6.4 Search Index Not Ready

```bash
# Rebuild indexes
curl -X POST http://127.0.0.1:8000/api/documents/index

# Check index stats
curl -s http://127.0.0.1:8000/api/documents/stats | python -m json.tool
```

### 6.5 FTS5 Errors

If FTS5 content gets out of sync with the base table:

```sql
-- Rebuild FTS5 index for materials
INSERT INTO materials_fts(materials_fts) VALUES('rebuild');

-- Rebuild FTS5 index for doc_chunks
INSERT INTO doc_chunks_fts(doc_chunks_fts) VALUES('rebuild');

-- Rebuild FTS5 index for invoice_items
INSERT INTO invoice_items_fts(invoice_items_fts) VALUES('rebuild');
```

### 6.6 Tests Failing

```bash
# Run specific test for diagnosis
pytest tests/path/to/test.py -v --tb=long

# Run with warnings visible
pytest -v -W default

# Check for import issues
python -c "from src.api.main import app; print('OK')"
```

---

## 7. Test Suite Summary

| Metric | Value |
|--------|-------|
| Total collected | 738 |
| Passed | 738 |
| Failed | 0 |
| Known failures | 0 (previously 4, fixed in Phase 8) |
| ruff errors | 0 |
| mypy errors | 0 (118 files) |
| Execution time | ~33s |

### Previously Known Failures (Fixed)

These 4 tests used `@patch` instead of `app.dependency_overrides` for FastAPI dependency injection, causing mock stores to not be injected:

- `test_company_documents.py::test_get_by_id_endpoint_exists` — Fixed
- `test_company_documents.py::test_delete_endpoint_exists` — Fixed
- `test_reminders.py::test_get_by_id_endpoint_exists` — Fixed
- `test_reminders.py::test_delete_endpoint_exists` — Fixed

### Deprecation Warnings (Low Priority)

| Warning | Source | Status |
|---------|--------|--------|
| `datetime.utcnow()` | 6 store files + entity defaults + fpdf2_renderer | Documented, fix in future session |
| `HTTP_422_UNPROCESSABLE_ENTITY` | Was in error_handler + routes | **Fixed** — replaced with literal `422` |
| SQLite date adapter deprecated (Python 3.12) | aiosqlite | Upstream dependency issue |

---

## 8. Changes Made in Phase 8

| Change | Files |
|--------|-------|
| Standardized `ErrorResponse` with `error_code`, `message`, `hint` fields | `src/application/dto/responses.py` |
| Updated error handler middleware with hints + SRGError.code extraction | `src/api/middleware/error_handler.py` |
| Fixed `HTTP_422_UNPROCESSABLE_ENTITY` deprecation | `error_handler.py`, `company_documents.py`, `reminders.py` |
| Fixed 4 known test failures (patch → dependency_overrides) | `tests/api/test_company_documents.py`, `tests/api/test_reminders.py` |
| Updated error field assertions in invoice tests | `tests/api/test_invoices.py` |
| Created this document | `docs/HARDENING.md` |
