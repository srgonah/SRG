<#
.SYNOPSIS
    SRG Verification Script - Run tests, lint, and type checks.

.DESCRIPTION
    Phase 1: Non-API tests (core, unit, infrastructure)
    Phase 2: API tests (api, integration)
    Phase 3: Lint (ruff)
    Phase 4: Type check (mypy - non-fatal)
    Phase 5: WebUI build (npm run build)
    Prints a clear PASS/FAIL summary at the end.

    Uses cmd /c execution to avoid false FAILs when commands print to stderr.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\tools\verify_all.ps1
#>

$ErrorActionPreference = "Continue"

# Set UTF-8 environment (fixes 'charmap' codec errors on Windows)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Results tracking
$results = @{
    "Phase1_NonAPI" = $null
    "Phase2_API" = $null
    "Phase3_Lint" = $null
    "Phase4_Mypy" = $null
    "Phase5_WebUI" = $null
}
$details = @{
    "Phase1_NonAPI" = ""
    "Phase2_API" = ""
    "Phase3_Lint" = ""
    "Phase4_Mypy" = ""
    "Phase5_WebUI" = ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SRG Verification Suite" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "(UTF-8 mode enabled)" -ForegroundColor Gray
Write-Host ""

# ============================================
# Phase 1: Non-API Tests
# ============================================
Write-Host "[Phase 1/5] Running non-API tests (core, unit, infrastructure)..." -ForegroundColor Yellow
Write-Host ""

$phase1Start = Get-Date
# Use cmd /c to avoid PowerShell NativeCommandError on stderr output
$phase1Output = cmd /c "python -m pytest -v tests/core tests/unit tests/infrastructure 2>&1"
$phase1Exit = $LASTEXITCODE
$phase1Output = $phase1Output -join "`n"
$phase1Duration = [math]::Round(((Get-Date) - $phase1Start).TotalSeconds, 1)

# Parse test counts from pytest output
$passedMatch = [regex]::Match($phase1Output, '(\d+) passed')
$failedMatch = [regex]::Match($phase1Output, '(\d+) failed')
$phase1Passed = if ($passedMatch.Success) { $passedMatch.Groups[1].Value } else { "?" }
$phase1Failed = if ($failedMatch.Success) { $failedMatch.Groups[1].Value } else { "0" }

if ($phase1Exit -eq 0) {
    $results["Phase1_NonAPI"] = $true
    Write-Host "  PASSED: $phase1Passed tests in ${phase1Duration}s" -ForegroundColor Green
    $details["Phase1_NonAPI"] = "$phase1Passed passed"
} else {
    $results["Phase1_NonAPI"] = $false
    Write-Host "  FAILED: $phase1Failed failed, $phase1Passed passed in ${phase1Duration}s" -ForegroundColor Red
    $details["Phase1_NonAPI"] = "$phase1Failed failed, $phase1Passed passed"
    # Show failure details
    $phase1Output -split "`n" | Where-Object { $_ -match "FAILED|ERROR" } | ForEach-Object {
        Write-Host "    $_" -ForegroundColor Red
    }
}
Write-Host ""

# ============================================
# Phase 2: API Tests
# ============================================
Write-Host "[Phase 2/5] Running API tests (api, integration)..." -ForegroundColor Yellow
Write-Host ""

$phase2Start = Get-Date
# Use cmd /c to avoid PowerShell NativeCommandError on stderr output
$phase2Output = cmd /c "python -m pytest -v tests/api tests/integration 2>&1"
$phase2Exit = $LASTEXITCODE
$phase2Output = $phase2Output -join "`n"
$phase2Duration = [math]::Round(((Get-Date) - $phase2Start).TotalSeconds, 1)

# Parse test counts
$passedMatch = [regex]::Match($phase2Output, '(\d+) passed')
$failedMatch = [regex]::Match($phase2Output, '(\d+) failed')
$phase2Passed = if ($passedMatch.Success) { $passedMatch.Groups[1].Value } else { "?" }
$phase2Failed = if ($failedMatch.Success) { $failedMatch.Groups[1].Value } else { "0" }

if ($phase2Exit -eq 0) {
    $results["Phase2_API"] = $true
    Write-Host "  PASSED: $phase2Passed tests in ${phase2Duration}s" -ForegroundColor Green
    $details["Phase2_API"] = "$phase2Passed passed"
} else {
    $results["Phase2_API"] = $false
    Write-Host "  FAILED: $phase2Failed failed, $phase2Passed passed in ${phase2Duration}s" -ForegroundColor Red
    $details["Phase2_API"] = "$phase2Failed failed, $phase2Passed passed"
    # Show failure details
    $phase2Output -split "`n" | Where-Object { $_ -match "FAILED|ERROR" } | ForEach-Object {
        Write-Host "    $_" -ForegroundColor Red
    }
}
Write-Host ""

# ============================================
# Phase 3: Lint (ruff)
# ============================================
Write-Host "[Phase 3/5] Running lint (ruff check)..." -ForegroundColor Yellow
Write-Host ""

$phase3Start = Get-Date
# Use cmd /c to avoid PowerShell NativeCommandError on stderr output
$phase3Output = cmd /c "python -m ruff check src tests 2>&1"
$phase3Exit = $LASTEXITCODE
$phase3Output = $phase3Output -join "`n"
$phase3Duration = [math]::Round(((Get-Date) - $phase3Start).TotalSeconds, 1)

if ($phase3Exit -eq 0) {
    $results["Phase3_Lint"] = $true
    Write-Host "  PASSED: No lint errors in ${phase3Duration}s" -ForegroundColor Green
    $details["Phase3_Lint"] = "0 errors"
} else {
    $results["Phase3_Lint"] = $false
    # Count errors
    $errorCount = ($phase3Output -split "`n" | Where-Object { $_ -match "^\s*src/|^\s*tests/" }).Count
    Write-Host "  FAILED: $errorCount lint error(s) in ${phase3Duration}s" -ForegroundColor Red
    $details["Phase3_Lint"] = "$errorCount errors"
    # Show first 10 errors
    $phase3Output -split "`n" | Select-Object -First 10 | ForEach-Object {
        Write-Host "    $_" -ForegroundColor Red
    }
}
Write-Host ""

# ============================================
# Phase 4: Type Check (mypy) - Non-fatal
# ============================================
Write-Host "[Phase 4/5] Running type check (mypy)..." -ForegroundColor Yellow
Write-Host "(Note: mypy failures do not fail the overall verification)" -ForegroundColor Gray
Write-Host ""

$phase4Start = Get-Date
# Use cmd /c to avoid PowerShell NativeCommandError on stderr output
$phase4Output = cmd /c "python -m mypy src 2>&1"
$phase4Exit = $LASTEXITCODE
$phase4Output = $phase4Output -join "`n"
$phase4Duration = [math]::Round(((Get-Date) - $phase4Start).TotalSeconds, 1)

# Parse error count
$errorMatch = [regex]::Match($phase4Output, 'Found (\d+) error')
$successMatch = $phase4Output -match "Success: no issues found"

if ($phase4Exit -eq 0 -or $successMatch) {
    $results["Phase4_Mypy"] = $true
    # Extract file count from success message
    $filesMatch = [regex]::Match($phase4Output, 'in (\d+) source file')
    $fileCount = if ($filesMatch.Success) { $filesMatch.Groups[1].Value } else { "?" }
    Write-Host "  PASSED: 0 errors in $fileCount files (${phase4Duration}s)" -ForegroundColor Green
    $details["Phase4_Mypy"] = "0 errors in $fileCount files"
} else {
    $results["Phase4_Mypy"] = $false
    $mypyErrors = if ($errorMatch.Success) { $errorMatch.Groups[1].Value } else { "?" }
    Write-Host "  INFO: $mypyErrors type error(s) in ${phase4Duration}s" -ForegroundColor Yellow
    $details["Phase4_Mypy"] = "$mypyErrors errors (non-fatal)"
    # Show first 5 errors
    $phase4Output -split "`n" | Where-Object { $_ -match "error:" } | Select-Object -First 5 | ForEach-Object {
        Write-Host "    $_" -ForegroundColor Yellow
    }
}
Write-Host ""

# ============================================
# Phase 5: WebUI Build
# ============================================
Write-Host "[Phase 5/5] Building WebUI (npm run build)..." -ForegroundColor Yellow
Write-Host ""

$WebuiDir = Join-Path $PSScriptRoot "..\webui"
$npmPath = Get-Command npm -ErrorAction SilentlyContinue

if (-not (Test-Path $WebuiDir)) {
    $results["Phase5_WebUI"] = $true
    Write-Host "  SKIPPED: webui/ directory not found." -ForegroundColor Gray
    $details["Phase5_WebUI"] = "skipped (no webui/)"
} elseif (-not $npmPath) {
    $results["Phase5_WebUI"] = $true
    Write-Host "  SKIPPED: npm not found." -ForegroundColor Gray
    $details["Phase5_WebUI"] = "skipped (no npm)"
} else {
    $phase5Start = Get-Date
    $savedDir = Get-Location
    Set-Location $WebuiDir

    # Use cmd /c to avoid PowerShell NativeCommandError on stderr output
    $phase5Output = cmd /c "npm run build 2>&1"
    $phase5Exit = $LASTEXITCODE

    Set-Location $savedDir
    $phase5Output = $phase5Output -join "`n"
    $phase5Duration = [math]::Round(((Get-Date) - $phase5Start).TotalSeconds, 1)

    if ($phase5Exit -eq 0) {
        $results["Phase5_WebUI"] = $true
        Write-Host "  PASSED: WebUI built successfully in ${phase5Duration}s" -ForegroundColor Green
        $details["Phase5_WebUI"] = "built in ${phase5Duration}s"
    } else {
        $results["Phase5_WebUI"] = $false
        Write-Host "  FAILED: WebUI build failed in ${phase5Duration}s" -ForegroundColor Red
        $details["Phase5_WebUI"] = "build failed"
        $phase5Output -split "`n" | Select-Object -Last 10 | ForEach-Object {
            Write-Host "    $_" -ForegroundColor Red
        }
    }
}
Write-Host ""

# ============================================
# Summary
# ============================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VERIFICATION SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allPassed = $results["Phase1_NonAPI"] -and $results["Phase2_API"] -and $results["Phase3_Lint"] -and $results["Phase5_WebUI"]
# Note: mypy is informational, not blocking

Write-Host "  Phase 1 (Non-API Tests):  " -NoNewline
if ($results["Phase1_NonAPI"]) {
    Write-Host "PASS" -ForegroundColor Green -NoNewline
} else {
    Write-Host "FAIL" -ForegroundColor Red -NoNewline
}
Write-Host "  [$($details["Phase1_NonAPI"])]" -ForegroundColor Gray

Write-Host "  Phase 2 (API Tests):      " -NoNewline
if ($results["Phase2_API"]) {
    Write-Host "PASS" -ForegroundColor Green -NoNewline
} else {
    Write-Host "FAIL" -ForegroundColor Red -NoNewline
}
Write-Host "  [$($details["Phase2_API"])]" -ForegroundColor Gray

Write-Host "  Phase 3 (Lint):           " -NoNewline
if ($results["Phase3_Lint"]) {
    Write-Host "PASS" -ForegroundColor Green -NoNewline
} else {
    Write-Host "FAIL" -ForegroundColor Red -NoNewline
}
Write-Host "  [$($details["Phase3_Lint"])]" -ForegroundColor Gray

Write-Host "  Phase 4 (Type Check):     " -NoNewline
if ($results["Phase4_Mypy"]) {
    Write-Host "PASS" -ForegroundColor Green -NoNewline
} else {
    Write-Host "INFO" -ForegroundColor Yellow -NoNewline
}
Write-Host "  [$($details["Phase4_Mypy"])]" -ForegroundColor Gray

Write-Host "  Phase 5 (WebUI Build):    " -NoNewline
if ($results["Phase5_WebUI"]) {
    Write-Host "PASS" -ForegroundColor Green -NoNewline
} else {
    Write-Host "FAIL" -ForegroundColor Red -NoNewline
}
Write-Host "  [$($details["Phase5_WebUI"])]" -ForegroundColor Gray

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if ($allPassed) {
    Write-Host "  OVERALL: PASS" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    exit 0
} else {
    Write-Host "  OVERALL: FAIL" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}
