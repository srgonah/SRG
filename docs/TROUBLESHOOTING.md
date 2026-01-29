# Troubleshooting

Common issues and their fixes for the SRG development environment.

---

## Quick Start (One Command)

```powershell
# Start everything (migrations + webui build + server)
powershell -ExecutionPolicy Bypass -File .\tools\run_all.ps1

# Skip frontend build (faster restart)
powershell -ExecutionPolicy Bypass -File .\tools\run_all.ps1 -SkipWebuiBuild

# Verify everything works
powershell -ExecutionPolicy Bypass -File .\tools\verify_all.ps1
```

---

## 'charmap' Codec Errors (UnicodeDecodeError)

### Symptom

```
UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 123
```

Or similar encoding errors when running Python commands on Windows.

### Cause

Windows uses cp1252 (Windows-1252) as the default encoding, but many files use UTF-8.

### Fix

Set UTF-8 environment variables before running Python:

```powershell
# Option 1: Set for current session
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Option 2: Set permanently (system-wide)
[System.Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
[System.Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "User")
```

The `run_all.ps1` and `verify_all.ps1` scripts set these automatically.

---

## EPERM esbuild Error (npm ci / npm install fails)

### Symptom

```
npm ERR! EPERM: operation not permitted, rename '...\esbuild.exe'
npm ERR! EPERM: operation not permitted, unlink '...\node_modules\.bin\esbuild'
```

### Cause

Another process (VS Code, antivirus, Windows Defender, or a stale node process) has a lock on the esbuild binary.

### Fix Procedure

```powershell
# Step 1: Close VS Code and any terminals in the webui folder

# Step 2: Kill all node processes
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force

# Step 3: Delete node_modules (may require elevated prompt if locked)
Remove-Item -Recurse -Force webui\node_modules -ErrorAction SilentlyContinue

# Step 4: If still failing, restart Windows Explorer (releases file handles)
Stop-Process -Name explorer -Force
Start-Process explorer

# Step 5: Try again
cd webui
npm ci
```

### Prevention

- Don't run `npm ci` while VS Code has the webui folder open
- Add `node_modules` to Windows Defender exclusions:
  ```powershell
  # Run as Administrator
  Add-MpPreference -ExclusionPath "C:\SrGonaH\SRG\webui\node_modules"
  ```

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

# 4. Start uvicorn with UTF-8 encoding and logs redirected
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Start-Process -NoNewWindow -FilePath python -ArgumentList `
    "-m", "uvicorn", "src.api.main:app",
    "--reload", "--host", "0.0.0.0", "--port", "8000" `
    -RedirectStandardOutput server.log `
    -RedirectStandardError  server_err.log

# 5. Wait a moment, then verify
Start-Sleep -Seconds 3
Invoke-RestMethod http://localhost:8000/api/health
```

You should see `status: healthy` in the output.

### Fix Procedure (Script)

Use the helper script:

```powershell
.\tools\restart_server.ps1
# or
.\tools\run_all.ps1 -SkipWebuiBuild
```

The script performs all steps above automatically and prints a summary.

### Prevention

- Always start the server with `.\tools\run_all.ps1` or `make dev`
  instead of running `uvicorn` directly.
- After switching branches, run `srg-migrate` (or `make migrate`) before
  starting the server.
- If using `--reload`, keep the terminal open — closing it orphans the process.

---

## Manual Health Checks

When something isn't working, run these checks in order:

### 1. Health Endpoint

```powershell
# Quick health check
Invoke-RestMethod http://localhost:8000/api/health

# Expected output:
# status           : healthy
# timestamp        : 2026-01-29T10:00:00.000000
# database         : connected
# ...
```

If this fails with connection refused, the server isn't running. See "Stale Server" above.

### 2. Database Connection

```powershell
# Check if database file exists
Test-Path data/srg.db

# Check database integrity
python -c "import sqlite3; c=sqlite3.connect('data/srg.db'); print(c.execute('PRAGMA integrity_check').fetchone())"
# Expected: ('ok',)

# Check migration status
python -m src.infrastructure.storage.sqlite.migrations.migrator
# Expected: "All migrations applied" or list of applied migrations
```

### 3. LLM Provider (Ollama)

```powershell
# Check if Ollama is running
Invoke-RestMethod http://localhost:11434/api/tags

# Expected: JSON with list of models
# If connection refused: Ollama is not running

# Start Ollama (if installed)
ollama serve

# Pull required model (if not present)
ollama pull llama3.2
```

### 4. API Endpoints

```powershell
# List invoices
Invoke-RestMethod http://localhost:8000/api/invoices

# List documents
Invoke-RestMethod http://localhost:8000/api/documents

# Chat health (requires LLM)
Invoke-RestMethod http://localhost:8000/api/chat/sessions
```

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

Or use `.\tools\run_all.ps1` which handles this automatically.

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

---

## Log File Locations

| File | Description |
|------|-------------|
| `server.log` | uvicorn stdout (access logs) |
| `server_err.log` | uvicorn stderr (errors, warnings) |
| `data/srg.db` | SQLite database |
| `data/documents/` | Uploaded document files |
| `webui/dist/` | Built frontend assets |

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `PYTHONUTF8` | Force UTF-8 encoding | `1` (set by scripts) |
| `PYTHONIOENCODING` | Python I/O encoding | `utf-8` (set by scripts) |
| `LLM_PROVIDER` | LLM backend | `ollama` |
| `LLM_MODEL` | Model name | `llama3.2` |
| `STORAGE_PATH` | Data directory | `./data` |

---

## Getting Help

If these steps don't resolve your issue:

1. Check `server.log` and `server_err.log` for error details
2. Run `.\tools\verify_all.ps1` to identify failing components
3. Open an issue with:
   - Error message / stack trace
   - Output of `python --version` and `node --version`
   - Operating system version
