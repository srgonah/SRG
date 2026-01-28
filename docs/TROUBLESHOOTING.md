# Troubleshooting

Common issues and their fixes for the SRG development environment.

---

## All Endpoints Return 500 (Stale Server)

### Symptom

Every endpoint — including `/api/health` — returns **500 Internal Server Error**
after pulling new code, running migrations, or editing source files. The uvicorn
`--reload` watcher either missed the change or a second uvicorn process is
shadowing the port.

### Cause

One or more stale `uvicorn` / `python` processes are still bound to port 8000,
serving an outdated version of the application. This happens most often on
Windows because:

- Closing a terminal does not always kill background processes.
- `--reload` can lose track of file changes after a migration or branch switch.
- A previous `Start-Process` / background job left an orphan.

### Fix Procedure (Manual)

Run these steps from the **SRG project root** in PowerShell:

```powershell
# 1. Kill every uvicorn process (safe — only affects dev servers)
Get-Process -Name uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force

# 2. Kill Python processes listening on port 8000
#    (avoids killing unrelated Python scripts)
$pids = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique
foreach ($pid in $pids) {
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

# 3. Run database migrations
python -m src.infrastructure.storage.sqlite.migrations.migrator

# 4. Start uvicorn with logs redirected to server.log
Start-Process -NoNewWindow -FilePath python -ArgumentList `
    "-m", "uvicorn", "src.api.main:app",
    "--reload", "--host", "0.0.0.0", "--port", "8000" `
    -RedirectStandardOutput server.log `
    -RedirectStandardError  server.err.log

# 5. Wait a moment, then verify
Start-Sleep -Seconds 3
Invoke-RestMethod http://localhost:8000/api/health
```

You should see `status: healthy` in the output.

### Fix Procedure (Script)

Use the helper script:

```powershell
.\tools\restart_server.ps1
```

The script performs all five steps above automatically and prints a summary.

### Prevention

- Always start the server with `.\tools\restart_server.ps1` or `make dev`
  instead of running `uvicorn` directly.
- After switching branches, run `srg-migrate` (or `make migrate`) before
  starting the server.
- If using `--reload`, keep the terminal open — closing it orphans the process.

---

## Database Migration Errors

### Symptom

Server starts but specific endpoints return 500 with `no such table` or
`no such column` in the logs.

### Cause

A new migration (e.g. `v006_matched_material_id.sql`) has not been applied.

### Fix

```powershell
python -m src.infrastructure.storage.sqlite.migrations.migrator
# or
srg-migrate
# or
make migrate
```

Then restart the server.

---

## Port 8000 Already in Use

### Symptom

```
ERROR:    [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)
```

### Fix

```powershell
# Find what is using port 8000
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
Get-Process -Id <pid>

# Kill it
Stop-Process -Id <pid> -Force
```

Or use `.\tools\restart_server.ps1` which handles this automatically.

---

## Tests Fail After Code Changes

### Quick checklist

```powershell
# 1. Install latest deps (picks up new packages like fpdf2)
pip install -e ".[dev]"

# 2. Run migrations (test fixtures create their own DBs, but verify)
srg-migrate

# 3. Run tests
pytest -v

# 4. Lint
ruff check src tests
```

### Known pre-existing failures

Four API smoke tests for `company_documents` and `reminders` (`test_get_by_id`,
`test_delete`) fail because those detail/delete endpoints are not yet
implemented. These are tracked and expected.
