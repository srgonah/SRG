# Smoke Test Runbook

Manual verification steps to confirm the SRG application is working after deployment or migration.

**Updated**: 2026-01-28

---

## Prerequisites

```powershell
# Install dependencies (dev mode)
pip install -e ".[dev]"
```

---

## 1. Start the Server

Use the automated runner script for reliable startup:

```powershell
# From repository root
powershell -ExecutionPolicy Bypass -File .\tools\run_all.ps1
```

This script will:
1. Kill any stale uvicorn processes
2. Run database migrations
3. Start the server on `127.0.0.1:8000`
4. Verify health endpoint returns 200
5. Print links to Swagger UI, OpenAPI, and log file

**Manual alternative** (if script unavailable):

```powershell
# Run migrations
python -m src.infrastructure.storage.sqlite.migrations.migrator

# Start server with log capture
Start-Process uvicorn -ArgumentList "src.api.main:app", "--host", "127.0.0.1", "--port", "8000" -RedirectStandardOutput server.log -RedirectStandardError server.log
```

---

## 2. Health Check

```powershell
# Basic health
curl -s http://127.0.0.1:8000/api/health

# Detailed health (includes LLM, DB, embedding status)
curl -s http://127.0.0.1:8000/api/health/detailed
```

**Expected**: `{"status": "ok", ...}` with HTTP 200

---

## 3. Reminders

```powershell
# List all reminders
curl -s http://127.0.0.1:8000/api/reminders

# List upcoming reminders (next 7 days)
curl -s "http://127.0.0.1:8000/api/reminders/upcoming?within_days=7"

# Get reminder insights
curl -s "http://127.0.0.1:8000/api/reminders/insights"
```

**Expected**: `{"reminders": [...], "total": N}` with HTTP 200

---

## 4. Company Documents

```powershell
# List all company documents
curl -s http://127.0.0.1:8000/api/company-documents

# List expiring documents (within 30 days)
curl -s "http://127.0.0.1:8000/api/company-documents/expiring?within_days=30"

# Trigger expiry check and auto-create reminders
curl -s -X POST "http://127.0.0.1:8000/api/company-documents/check-expiry?within_days=30"
```

**Expected**: `{"documents": [...], "total": N}` with HTTP 200

---

## 5. Invoices

```powershell
# List all invoices
curl -s http://127.0.0.1:8000/api/invoices

# Get specific invoice (replace {id} with actual ID)
curl -s http://127.0.0.1:8000/api/invoices/{id}

# Upload an invoice (if you have a test PDF)
curl -X POST http://127.0.0.1:8000/api/invoices/upload -F "file=@test_invoice.pdf"
```

**Expected**: `{"invoices": [...], "total": N, "limit": 20, "offset": 0}` with HTTP 200

---

## 6. Catalog

```powershell
# List all materials
curl -s http://127.0.0.1:8000/api/catalog/

# Search materials by name
curl -s "http://127.0.0.1:8000/api/catalog/?q=cable"

# Get specific material (replace {id})
curl -s http://127.0.0.1:8000/api/catalog/{id}
```

**Expected**: `{"materials": [...], "total": N}` with HTTP 200

---

## 7. Price History & Statistics

```powershell
# Get price statistics
curl -s http://127.0.0.1:8000/api/prices/stats

# Get price history (with optional filters)
curl -s "http://127.0.0.1:8000/api/prices/history?limit=50"

# Filter by item name
curl -s "http://127.0.0.1:8000/api/prices/history?item=cable"
```

**Expected (stats)**: `{"stats": [...], "total": N}` with HTTP 200
**Expected (history)**: `{"entries": [...], "total": N}` with HTTP 200

---

## 8. Inventory

```powershell
# Get inventory status
curl -s http://127.0.0.1:8000/api/inventory/status

# Get movements for item (replace {id})
curl -s http://127.0.0.1:8000/api/inventory/{id}/movements
```

**Expected**: `{"items": [...], "total": N}` with HTTP 200

---

## 9. Sales

```powershell
# List sales invoices
curl -s http://127.0.0.1:8000/api/sales/invoices
```

**Expected**: `{"invoices": [...], "total": N}` with HTTP 200

---

## 10. Search & Chat

```powershell
# Quick search
curl -s "http://127.0.0.1:8000/api/search/quick?q=invoice"

# List chat sessions
curl -s http://127.0.0.1:8000/api/sessions
```

**Expected**: JSON response with results/sessions array

---

## Quick All-in-One Check

Copy and paste this block to verify all major endpoints:

```powershell
Write-Host "=== Health ===" -ForegroundColor Cyan
curl -s http://127.0.0.1:8000/api/health
Write-Host "`n=== Reminders ===" -ForegroundColor Cyan
curl -s http://127.0.0.1:8000/api/reminders
Write-Host "`n=== Company Docs ===" -ForegroundColor Cyan
curl -s http://127.0.0.1:8000/api/company-documents
Write-Host "`n=== Invoices ===" -ForegroundColor Cyan
curl -s http://127.0.0.1:8000/api/invoices
Write-Host "`n=== Catalog ===" -ForegroundColor Cyan
curl -s http://127.0.0.1:8000/api/catalog/
Write-Host "`n=== Price Stats ===" -ForegroundColor Cyan
curl -s http://127.0.0.1:8000/api/prices/stats
Write-Host "`n=== Inventory ===" -ForegroundColor Cyan
curl -s http://127.0.0.1:8000/api/inventory/status
Write-Host "`n=== Sales ===" -ForegroundColor Cyan
curl -s http://127.0.0.1:8000/api/sales/invoices
Write-Host "`n=== DONE ===" -ForegroundColor Green
```

All endpoints should return HTTP 200 with valid JSON.

---

## Automated Verification

Run the full test suite:

```powershell
# Full verification (tests + lint + type check)
powershell -ExecutionPolicy Bypass -File .\tools\verify_all.ps1

# Or run individual phases manually:
python -m pytest -v tests/core tests/unit tests/infrastructure  # Non-API tests
python -m pytest -v tests/api tests/integration                  # API tests
python -m ruff check src tests                                   # Lint
python -m mypy src                                               # Type check
```

**Expected**: ~891 tests pass, 0 ruff errors, 0 mypy errors

---

## Troubleshooting

### Stale uvicorn processes

If the server won't start or port 8000 is busy:

```powershell
# Kill all uvicorn processes
Get-Process -Name uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force

# Check what's using port 8000
netstat -ano | Select-String ":8000"

# Kill process by PID (replace with actual PID)
Stop-Process -Id <PID> -Force
```

### Check server logs

```powershell
# View last 50 lines of server log
Get-Content server.log -Tail 50

# Follow log in real-time
Get-Content server.log -Wait -Tail 20
```

### Database issues

```powershell
# Re-run migrations
python -m src.infrastructure.storage.sqlite.migrations.migrator

# Check migration status
# (Migrations are in data/srg.db, schema_migrations table)
```

### Common error codes

| Error | Meaning | Fix |
|-------|---------|-----|
| `INVOICE_NOT_FOUND` | Invoice ID doesn't exist | Check ID, list invoices first |
| `MATERIAL_NOT_FOUND` | Material ID doesn't exist | Check ID, list catalog first |
| `INSUFFICIENT_STOCK` | Not enough inventory | Check stock levels |
| `LLM_UNAVAILABLE` | Ollama not running | Start Ollama service |

See `docs/TROUBLESHOOTING.md` for more details.
