<#
.SYNOPSIS
    Restart the SRG development server cleanly.

.DESCRIPTION
    Kills stale uvicorn / Python-on-port-8000 processes, runs database
    migrations, starts uvicorn with --reload, and verifies /api/health.

    Logs are written to server.log and server.err.log in the project root.

.EXAMPLE
    .\tools\restart_server.ps1
    .\tools\restart_server.ps1 -Port 8080
    .\tools\restart_server.ps1 -SkipMigrate
#>

param(
    [int]$Port = 8000,
    [switch]$SkipMigrate
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Push-Location $projectRoot

Write-Host ""
Write-Host "=== SRG Server Restart ===" -ForegroundColor Cyan
Write-Host "Project root: $projectRoot"
Write-Host ""

# ---------------------------------------------------------------
# 1. Stop stale processes
# ---------------------------------------------------------------
Write-Host "[1/4] Stopping stale processes..." -ForegroundColor Yellow

# Kill uvicorn.exe processes
$uvicornProcs = Get-Process -Name uvicorn -ErrorAction SilentlyContinue
if ($uvicornProcs) {
    $uvicornProcs | Stop-Process -Force
    Write-Host "      Killed $($uvicornProcs.Count) uvicorn process(es)."
} else {
    Write-Host "      No uvicorn processes found."
}

# Kill Python processes bound to the target port
try {
    $portPids = (Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue).OwningProcess |
        Sort-Object -Unique
    if ($portPids) {
        foreach ($pid in $portPids) {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "      Killing PID $pid ($($proc.ProcessName)) on port $Port."
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        }
    } else {
        Write-Host "      Port $Port is free."
    }
} catch {
    Write-Host "      Could not check port $Port (requires admin for Get-NetTCPConnection)." -ForegroundColor DarkYellow
}

Start-Sleep -Seconds 1

# ---------------------------------------------------------------
# 2. Run migrations
# ---------------------------------------------------------------
if (-not $SkipMigrate) {
    Write-Host "[2/4] Running database migrations..." -ForegroundColor Yellow
    python -m src.infrastructure.storage.sqlite.migrations.migrator
    if ($LASTEXITCODE -ne 0) {
        Write-Host "      Migration failed (exit code $LASTEXITCODE)." -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Write-Host "      Migrations applied."
} else {
    Write-Host "[2/4] Skipping migrations (-SkipMigrate)." -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------
# 3. Start uvicorn
# ---------------------------------------------------------------
Write-Host "[3/4] Starting uvicorn on port $Port..." -ForegroundColor Yellow

$logFile    = Join-Path $projectRoot "server.log"
$errLogFile = Join-Path $projectRoot "server.err.log"

Start-Process -NoNewWindow -FilePath python -ArgumentList `
    "-m", "uvicorn", "src.api.main:app",
    "--reload", "--host", "0.0.0.0", "--port", "$Port" `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError  $errLogFile

Write-Host "      Logs:   $logFile"
Write-Host "      Errors: $errLogFile"

# ---------------------------------------------------------------
# 4. Health check
# ---------------------------------------------------------------
Write-Host "[4/4] Waiting for server..." -ForegroundColor Yellow

$maxAttempts = 10
$healthy = $false

for ($i = 1; $i -le $maxAttempts; $i++) {
    Start-Sleep -Seconds 2
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:$Port/api/health" -TimeoutSec 5
        if ($resp.status -eq "healthy") {
            $healthy = $true
            break
        }
    } catch {
        Write-Host "      Attempt $i/$maxAttempts - not ready yet..."
    }
}

Write-Host ""
if ($healthy) {
    Write-Host "Server is UP on http://localhost:$Port" -ForegroundColor Green
    Write-Host "  Health:  /api/health      -> $($resp.status)"
    Write-Host "  Docs:    http://localhost:$Port/docs"
    Write-Host ""
} else {
    Write-Host "Server did NOT become healthy after $maxAttempts attempts." -ForegroundColor Red
    Write-Host "Check server.err.log for details:"
    Write-Host ""
    if (Test-Path $errLogFile) {
        Get-Content $errLogFile -Tail 20
    }
    Pop-Location
    exit 1
}

Pop-Location
