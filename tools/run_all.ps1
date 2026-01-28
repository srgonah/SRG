<#
.SYNOPSIS
    SRG Close-Out Runner - Clean server restart with health verification.

.DESCRIPTION
    1) Kill stale uvicorn processes safely
    2) Run DB migrations
    3) Start server on 127.0.0.1:8000
    4) Redirect stdout+stderr to server.log
    5) Verify health endpoint returns 200
    6) Print useful links

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\tools\run_all.ps1
#>

$ErrorActionPreference = "Stop"

# Configuration
$ServerHost = "127.0.0.1"
$ServerPort = 8000
$LogFile = "server.log"
$HealthTimeout = 30  # seconds

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SRG Close-Out Runner" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Kill stale uvicorn processes
Write-Host "[1/5] Killing stale uvicorn processes..." -ForegroundColor Yellow
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
Write-Host "[2/5] Running database migrations..." -ForegroundColor Yellow
# Use cmd.exe to avoid PowerShell NativeCommandError on stderr warnings
$migrationOutput = cmd /c "python -m src.infrastructure.storage.sqlite.migrations.migrator 2>&1"
$migrationExit = $LASTEXITCODE
if ($migrationExit -ne 0) {
    Write-Host "       Migration failed!" -ForegroundColor Red
    $migrationOutput | ForEach-Object { Write-Host "       $_" -ForegroundColor Red }
    exit 1
}
Write-Host "       Migrations complete." -ForegroundColor Green

# Step 3: Clear old log file
Write-Host ""
Write-Host "[3/5] Starting uvicorn server..." -ForegroundColor Yellow
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

# Step 4: Wait for server startup and verify health
Write-Host ""
Write-Host "[4/5] Waiting for server to be ready..." -ForegroundColor Yellow

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

# Step 5: Print useful links
Write-Host ""
Write-Host "[5/5] Server is ready!" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  SRG Server Running" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Swagger UI:  http://${ServerHost}:${ServerPort}/docs" -ForegroundColor Cyan
Write-Host "  OpenAPI:     http://${ServerHost}:${ServerPort}/openapi.json" -ForegroundColor Cyan
Write-Host "  Health:      http://${ServerHost}:${ServerPort}/api/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Log file:    $((Resolve-Path $LogFile).Path)" -ForegroundColor Gray
Write-Host "  Server PID:  $($serverProcess.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "  To stop:     Stop-Process -Id $($serverProcess.Id)" -ForegroundColor Gray
Write-Host ""
