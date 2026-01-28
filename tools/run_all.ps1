<#
.SYNOPSIS
    SRG Close-Out Runner - Build WebUI, migrate DB, start server with health verification.

.DESCRIPTION
    1) Kill stale uvicorn processes safely
    2) Run DB migrations
    3) Build React WebUI (webui/dist) — skip with -SkipWebuiBuild
    4) Start server on 127.0.0.1:8000
    5) Verify health endpoint returns 200
    6) Print useful links

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
$LogFile = "server.log"
$HealthTimeout = 30  # seconds
$WebuiDir = Join-Path $PSScriptRoot "..\webui"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SRG Close-Out Runner" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Kill stale uvicorn processes
Write-Host "[1/6] Killing stale uvicorn processes..." -ForegroundColor Yellow
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

# Also check for processes bound to the port
$portInUse = netstat -ano 2>$null | Select-String ":$ServerPort\s" | Select-String "LISTENING"
if ($portInUse) {
    Write-Host "       Warning: Port $ServerPort may still be in use." -ForegroundColor Yellow
    Write-Host "       Waiting 3 seconds for port release..." -ForegroundColor Gray
    Start-Sleep -Seconds 3
}

# Step 2: Run DB migrations
Write-Host ""
Write-Host "[2/6] Running database migrations..." -ForegroundColor Yellow
# Use cmd.exe to avoid PowerShell NativeCommandError on stderr warnings
$migrationOutput = cmd /c "python -m src.infrastructure.storage.sqlite.migrations.migrator 2>&1"
$migrationExit = $LASTEXITCODE
if ($migrationExit -ne 0) {
    Write-Host "       Migration failed!" -ForegroundColor Red
    $migrationOutput | ForEach-Object { Write-Host "       $_" -ForegroundColor Red }
    exit 1
}
Write-Host "       Migrations complete." -ForegroundColor Green

# Step 3: Build WebUI
Write-Host ""
Write-Host "[3/6] Building React WebUI..." -ForegroundColor Yellow

if ($SkipWebuiBuild) {
    Write-Host "       Skipped (-SkipWebuiBuild flag)." -ForegroundColor Gray
} elseif (-not (Test-Path $WebuiDir)) {
    Write-Host "       Skipped (webui/ directory not found)." -ForegroundColor Gray
} else {
    # Check if npm is available
    $npmPath = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npmPath) {
        Write-Host "       npm not found. Skipping WebUI build." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "       To enable WebUI builds, install Node.js LTS:" -ForegroundColor Gray
        Write-Host "         https://nodejs.org/ (download the LTS version)" -ForegroundColor Gray
        Write-Host "         Or: winget install OpenJS.NodeJS.LTS" -ForegroundColor Gray
        Write-Host ""
        Write-Host "       After installing, re-run this script." -ForegroundColor Gray
    } else {
        $savedDir = Get-Location
        Set-Location $WebuiDir

        # Install dependencies (clean install for reproducibility)
        Write-Host "       Running npm ci..." -ForegroundColor Gray
        $npmCiOutput = cmd /c "npm ci 2>&1"
        $npmCiExit = $LASTEXITCODE
        if ($npmCiExit -ne 0) {
            Write-Host "       npm ci failed!" -ForegroundColor Red
            $npmCiOutput | ForEach-Object { Write-Host "       $_" -ForegroundColor Red }
            Set-Location $savedDir
            exit 1
        }

        # Build
        Write-Host "       Running npm run build..." -ForegroundColor Gray
        $npmBuildOutput = cmd /c "npm run build 2>&1"
        $npmBuildExit = $LASTEXITCODE
        if ($npmBuildExit -ne 0) {
            Write-Host "       npm run build failed!" -ForegroundColor Red
            $npmBuildOutput | ForEach-Object { Write-Host "       $_" -ForegroundColor Red }
            Set-Location $savedDir
            exit 1
        }

        Set-Location $savedDir
        Write-Host "       WebUI built to webui/dist/." -ForegroundColor Green
    }
}

# Step 4: Start server
Write-Host ""
Write-Host "[4/6] Starting uvicorn server..." -ForegroundColor Yellow
if (Test-Path $LogFile) {
    Remove-Item $LogFile -Force
}

# Start server in background with output redirected to log file
$stderrLog = "server_err.log"
$serverProcess = Start-Process -FilePath "uvicorn" `
    -ArgumentList "src.api.main:app", "--host", $ServerHost, "--port", $ServerPort `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError $stderrLog `
    -PassThru `
    -WindowStyle Hidden

Write-Host "       Server started (PID: $($serverProcess.Id))" -ForegroundColor Green
Write-Host "       Logging to: $LogFile" -ForegroundColor Gray

# Step 5: Wait for server startup and verify health
Write-Host ""
Write-Host "[5/6] Waiting for server to be ready..." -ForegroundColor Yellow

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
        # Server not ready yet, continue waiting
        Write-Host "." -NoNewline -ForegroundColor Gray
    }
}

Write-Host ""

if (-not $isHealthy) {
    Write-Host "       FAILED: Health check did not return 200 within $HealthTimeout seconds." -ForegroundColor Red
    Write-Host ""
    Write-Host "       Check $LogFile for errors:" -ForegroundColor Yellow
    if (Test-Path $LogFile) {
        Get-Content $LogFile -Tail 20
    }
    exit 1
}

$elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
Write-Host "       Health check passed in ${elapsed}s" -ForegroundColor Green

# Step 6: Print useful links
Write-Host ""
Write-Host "[6/6] Server is ready!" -ForegroundColor Yellow
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
Write-Host "  Log file:    $((Resolve-Path $LogFile).Path)" -ForegroundColor Gray
Write-Host "  Server PID:  $($serverProcess.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "  To stop:     Stop-Process -Id $($serverProcess.Id)" -ForegroundColor Gray
Write-Host ""
