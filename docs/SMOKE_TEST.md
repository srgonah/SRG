# Smoke Test Runbook

Manual verification steps to confirm the SRG application is working after deployment or migration.

---

## Prerequisites

```bash
# Install dependencies
pip install -e ".[dev]"

# Run database migrations
python -m src.infrastructure.storage.sqlite.migrations.migrator
```

---

## 1. Start the Server

```bash
# Start with auto-reload (development)
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Or start with log capture (background)
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```

Wait a few seconds for startup, then proceed.

---

## 2. Health Check

```bash
curl -s http://127.0.0.1:8000/api/health
```

Expected: `{"status": "ok", ...}`

```bash
curl -s http://127.0.0.1:8000/api/health/detailed
```

Expected: JSON with `status`, `version`, `uptime_seconds`, and provider health info.

---

## 3. Invoices

```bash
# List invoices
curl -s http://127.0.0.1:8000/api/invoices

# Upload an invoice (if you have a test PDF)
curl -X POST http://127.0.0.1:8000/api/invoices/upload \
  -F "file=@test_invoice.pdf" \
  -F "auto_audit=true"
```

Expected (list): `{"invoices": [...], "total": N, "limit": 20, "offset": 0}`

---

## 4. Catalog

```bash
# List materials
curl -s http://127.0.0.1:8000/api/catalog/

# Search materials
curl -s "http://127.0.0.1:8000/api/catalog/?q=cable"
```

Expected: `{"materials": [...], "total": N}`

---

## 5. Prices

```bash
# Price statistics
curl -s "http://127.0.0.1:8000/api/prices/stats"

# Price history (with optional filters)
curl -s "http://127.0.0.1:8000/api/prices/history?item=cable"
```

Expected (stats): `{"stats": [...], "total": N}`
Expected (history): `{"entries": [...], "total": N}`

---

## 6. Company Documents

```bash
# List company documents
curl -s http://127.0.0.1:8000/api/company-documents

# List expiring documents
curl -s "http://127.0.0.1:8000/api/company-documents/expiring?within_days=30"
```

Expected: `{"documents": [...], "total": N}`

---

## 7. Reminders

```bash
# List reminders
curl -s http://127.0.0.1:8000/api/reminders

# List upcoming reminders
curl -s "http://127.0.0.1:8000/api/reminders/upcoming?within_days=7"
```

Expected: `{"reminders": [...], "total": N}`

---

## 8. Search

```bash
# Quick search
curl -s "http://127.0.0.1:8000/api/search/quick?q=invoice"
```

Expected: JSON with `results` array and `total`.

---

## 9. Sessions

```bash
# List chat sessions
curl -s http://127.0.0.1:8000/api/sessions
```

Expected: `{"sessions": [...], "total": N}`

---

## Quick All-in-One (copy-paste)

```bash
echo "=== Health ===" && \
curl -s http://127.0.0.1:8000/api/health && echo && \
echo "=== Invoices ===" && \
curl -s http://127.0.0.1:8000/api/invoices && echo && \
echo "=== Catalog ===" && \
curl -s http://127.0.0.1:8000/api/catalog/ && echo && \
echo "=== Price Stats ===" && \
curl -s http://127.0.0.1:8000/api/prices/stats && echo && \
echo "=== Company Docs ===" && \
curl -s http://127.0.0.1:8000/api/company-documents && echo && \
echo "=== Reminders ===" && \
curl -s http://127.0.0.1:8000/api/reminders && echo && \
echo "=== DONE ==="
```

All endpoints should return HTTP 200 with valid JSON. If any return 500, check `server.log` or see `docs/TROUBLESHOOTING.md`.

---

## Automated Tests

```bash
# Full suite
pytest -v

# Quick subset (no app startup overhead)
pytest tests/core/ tests/unit/ tests/infrastructure/ -q

# API tests only
pytest tests/api/ -q

# Integration tests only
pytest tests/integration/ -q
```

Expected: 738 pass, 0 fail.
