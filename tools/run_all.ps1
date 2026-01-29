<#
.SYNOPSIS
    SRG Close-Out Runner - Build WebUI, migrate DB, start server with health verification.

.DESCRIPTION
    1) Set UTF-8 environment to avoid charmap codec issues
    2) Kill stale uvicorn processes safely
    3) Run DB migrations
    4) Build React WebUI (webui/dist) — skip with -SkipWebuiBuild
    5) Start server on 127.0.0.1:8000
    6) Verify health endpoint returns 200
    7) Print useful links

.PARAMETER SkipWebuiBuild
    Skip the npm ci / npm run build step. Useful when the frontend is already built
    or you only want to restart the backend quickly.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\tools\run_all.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\tools\run_all.ps1 -SkipWebuiBuild
#>

param(
    [switch]$SkipWebuiBuild
)

$ErrorActionPreference = "Stop"

# Configuration
$ServerHost = "127.0.0.1"
$ServerPort = 8000
$LogFile = Join-Path $PSScriptRoot "..\server.log"
$StderrLog = Join-Path $PSScriptRoot "..\server_err.log"
$HealthTimeout = 30  # seconds
$WebuiDir = Join-Path $PSScriptRoot "..\webui"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SRG Close-Out Runner" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Set UTF-8 environment (fixes 'charmap' codec errors on Windows)
Write-Host "[1/7] Setting UTF-8 environment..." -ForegroundColor Yellow
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Host "       PYTHONUTF8=1, PYTHONIOENCODING=utf-8" -ForegroundColor Green

# Step 2: Kill stale uvicorn processes
Write-Host ""
Write-Host "[2/7] Killing stale uvicorn processes..." -ForegroundColor Yellow
$uvicornProcesses = Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue
if ($uvicornProcesses) {
    $count = ($uvicornProcesses | Measure-Object).Count
    Write-Host "       Found $count uvicorn process(es). Stopping..." -ForegroundColor Gray
    $uvicornProcesses | Stop-Process -Force
    Start-Sleep -Seconds 2
    Write-Host "       Stopped." -ForegroundColor Green
} else {
    Write-Host "       No stale uvicorn processes found." -ForegroundColor Green
}

# Also kill Python processes bound to the port
try {
    $pids = (Get-NetTCPConnection -LocalPort $ServerPort -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique
    foreach ($pid in $pids) {
        if ($pid -and $pid -ne 0) {
            Write-Host "       Killing process $pid on port $ServerPort..." -ForegroundColor Gray
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    # Ignore errors if port is not in use
}

# Wait for port release
$portInUse = netstat -ano 2>$null | Select-String ":$ServerPort\s" | Select-String "LISTENING"
if ($portInUse) {
    Write-Host "       Waiting 3 seconds for port release..." -ForegroundColor Gray
    Start-Sleep -Seconds 3
}

# Step 3: Run DB migrations
Write-Host ""
Write-Host "[3/7] Running database migrations..." -ForegroundColor Yellow
$migrationOutput = cmd /c "python -m src.infrastructure.storage.sqlite.migrations.migrator 2>&1"
$migrationExit = $LASTEXITCODE
if ($migrationExit -ne 0) {
    Write-Host "       Migration failed!" -ForegroundColor Red
    $migrationOutput | ForEach-Object { Write-Host "       $_" -ForegroundColor Red }
    exit 1
}
Write-Host "       Migrations complete." -ForegroundColor Green

# Step 4: Build WebUI (non-fatal - backend starts even if build fails)
Write-Host ""
Write-Host "[4/7] Building React WebUI..." -ForegroundColor Yellow

$webuiBuildFailed = $false
$webuiBuildError = ""

if ($SkipWebuiBuild) {
    Write-Host "       Skipped (-SkipWebuiBuild flag)." -ForegroundColor Gray
} elseif (-not (Test-Path $WebuiDir)) {
    Write-Host "       Skipped (webui/ directory not found)." -ForegroundColor Gray
} else {
    $npmPath = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npmPath) {
        Write-Host "       npm not found. Skipping WebUI build." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "       To enable WebUI builds, install Node.js LTS:" -ForegroundColor Gray
        Write-Host "         https://nodejs.org/ (download the LTS version)" -ForegroundColor Gray
        Write-Host "         Or: winget install OpenJS.NodeJS.LTS" -ForegroundColor Gray
    } else {
        $savedDir = Get-Location
        Set-Location $WebuiDir

        # Install dependencies
        Write-Host "       Running npm ci..." -ForegroundColor Gray
        $npmCiOutput = cmd /c "npm ci 2>&1"
        $npmCiExit = $LASTEXITCODE
        if ($npmCiExit -ne 0) {
            Write-Host "       npm ci failed (non-fatal, continuing with backend)." -ForegroundColor Yellow
            $webuiBuildFailed = $true
            $webuiBuildError = "npm ci failed"
            # Show last few lines of error
            $npmCiOutput | Select-Object -Last 5 | ForEach-Object { Write-Host "       $_" -ForegroundColor Yellow }
        } else {
            # Build
            Write-Host "       Running npm run build..." -ForegroundColor Gray
            $npmBuildOutput = cmd /c "npm run build 2>&1"
            $npmBuildExit = $LASTEXITCODE
            if ($npmBuildExit -ne 0) {
                Write-Host "       npm run build failed (non-fatal, continuing with backend)." -ForegroundColor Yellow
                $webuiBuildFailed = $true
                $webuiBuildError = "npm run build failed"
                # Show last few lines of error
                $npmBuildOutput | Select-Object -Last 5 | ForEach-Object { Write-Host "       $_" -ForegroundColor Yellow }
            } else {
                Write-Host "       WebUI built to webui/dist/." -ForegroundColor Green
            }
        }

        Set-Location $savedDir
    }
}

# Step 5: Start server
Write-Host ""
Write-Host "[5/7] Starting uvicorn server..." -ForegroundColor Yellow

# Clean up old log files
if (Test-Path $LogFile) { Remove-Item $LogFile -Force }
if (Test-Path $StderrLog) { Remove-Item $StderrLog -Force }

# Create empty log files to ensure they exist
New-Item -Path $LogFile -ItemType File -Force | Out-Null
New-Item -Path $StderrLog -ItemType File -Force | Out-Null

# Start server in background with UTF-8 environment and output redirected
$serverProcess = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "set PYTHONUTF8=1 && set PYTHONIOENCODING=utf-8 && uvicorn src.api.main:app --host $ServerHost --port $ServerPort" `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError $StderrLog `
    -PassThru `
    -WindowStyle Hidden

Write-Host "       Server started (PID: $($serverProcess.Id))" -ForegroundColor Green
Write-Host "       Logging to: $LogFile" -ForegroundColor Gray

# Step 6: Wait for server startup and verify health
Write-Host ""
Write-Host "[6/7] Waiting for server to be ready..." -ForegroundColor Yellow

$healthUrl = "http://${ServerHost}:${ServerPort}/api/health"
$startTime = Get-Date
$isHealthy = $false

while (((Get-Date) - $startTime).TotalSeconds -lt $HealthTimeout) {
    Start-Sleep -Milliseconds 500
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $isHealthy = $true
            break
        }
    } catch {
        Write-Host "." -NoNewline -ForegroundColor Gray
    }
}

Write-Host ""

if (-not $isHealthy) {
    Write-Host "       FAILED: Health check did not return 200 within $HealthTimeout seconds." -ForegroundColor Red
    Write-Host ""
    Write-Host "       Check logs for errors:" -ForegroundColor Yellow
    if (Test-Path $LogFile) {
        Write-Host "       --- stdout ($LogFile) ---" -ForegroundColor Gray
        Get-Content $LogFile -Tail 15 | ForEach-Object { Write-Host "       $_" }
    }
    if (Test-Path $StderrLog) {
        Write-Host "       --- stderr ($StderrLog) ---" -ForegroundColor Gray
        Get-Content $StderrLog -Tail 15 | ForEach-Object { Write-Host "       $_" }
    }
    exit 1
}

$elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
Write-Host "       Health check passed in ${elapsed}s" -ForegroundColor Green

# Step 7: Print useful links
Write-Host ""
Write-Host "[7/7] Server is ready!" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  SRG Server Running" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Web UI:      http://${ServerHost}:${ServerPort}/" -ForegroundColor Cyan
Write-Host "  Swagger UI:  http://${ServerHost}:${ServerPort}/docs" -ForegroundColor Cyan
Write-Host "  OpenAPI:     http://${ServerHost}:${ServerPort}/openapi.json" -ForegroundColor Cyan
Write-Host "  Health:      http://${ServerHost}:${ServerPort}/api/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Log file:    $LogFile" -ForegroundColor Gray
Write-Host "  Error log:   $StderrLog" -ForegroundColor Gray
Write-Host "  Server PID:  $($serverProcess.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "  To stop:     Stop-Process -Id $($serverProcess.Id)" -ForegroundColor Gray
Write-Host ""

if ($webuiBuildFailed) {
    Write-Host "  WARNING: WebUI build failed ($webuiBuildError)" -ForegroundColor Yellow
    Write-Host "           API is running but frontend may be stale." -ForegroundColor Yellow
    Write-Host "           Fix issues and re-run, or use -SkipWebuiBuild." -ForegroundColor Yellow
    Write-Host ""
}
