#!/usr/bin/env pwsh
# Check results of async DAB query runs.
# Run from: C:\Users\VikasVijigiri\Documents\TT_SQL_V2\backend\agent
#
# Usage:
#   .\check_dab_results.ps1              # check latest async_v2.log
#   .\check_dab_results.ps1 -Log async_concurrent.log

param([string]$Log = "async_v2.log")

$logDir = "$PSScriptRoot\dab_parallel_logs"
$logFile = "$logDir\$Log"

Write-Host "`n=== DAB Async Run Status ===" -ForegroundColor Cyan
Write-Host "Active python processes: $((Get-Process python -ErrorAction SilentlyContinue).Count)"
Write-Host "Log file : $logFile"

if (-not (Test-Path $logFile)) {
    Write-Host "Log file not found!" -ForegroundColor Red
    exit 1
}

$sz  = [math]::Round((Get-Item $logFile).Length / 1024, 1)
$mt  = (Get-Item $logFile).LastWriteTime
$content = Get-Content $logFile -Raw -Encoding utf8 -ErrorAction SilentlyContinue
$clean   = $content -replace '\x1B\[[0-9;]*[mK]', ''
$lines   = $clean -split "`n"

# Concurrency proof: max log lines per second
$maxPerSec = $lines | Where-Object { $_ -match "\d\d:\d\d:\d\d" } |
    Group-Object { if ($_ -match "(\d\d:\d\d:\d\d)") { $Matches[1] } else { "" } } |
    Sort-Object Count -Descending | Select-Object -First 1
Write-Host "Peak concurrent log lines/sec: $($maxPerSec.Count) @ $($maxPerSec.Name)" -ForegroundColor Green

# Counts
$passed   = ($clean | Select-String "\[PASS\]").Matches.Count
$failed   = ($clean | Select-String "\[FAIL\]").Matches.Count
$errors   = ($clean | Select-String "\[ERROR\]").Matches.Count
$idxWarn  = ($clean | Select-String "WARNING.*IndexSeeding|IndexSeeding.*WARNING|AttributeError").Matches.Count
$probeErr = ($clean | Select-String "EXECUTION PROBE ERROR").Matches.Count
$integrity= ($clean | Select-String "\[PromptIntegrity\]").Matches.Count

Write-Host "`nResults: " -NoNewline
Write-Host "PASS=$passed" -ForegroundColor Green -NoNewline
Write-Host "  FAIL=$failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Gray" }) -NoNewline
Write-Host "  ERROR=$errors" -ForegroundColor $(if ($errors -gt 0) { "Red" } else { "Gray" })

Write-Host "`nQuality signals:"
Write-Host "  IndexSeeding warnings : $idxWarn  $(if ($idxWarn -eq 0) { '[OK]' } else { '[WARN]' })"
Write-Host "  Execution probe errors: $probeErr"
Write-Host "  PromptIntegrity fires : $integrity"

# Extract PASS/FAIL lines
$resultLines = $lines | Where-Object { $_ -match "\[PASS\]|\[FAIL\]|\[ERROR\]" }
if ($resultLines) {
    Write-Host "`nResult details:"
    $resultLines | ForEach-Object { Write-Host "  $_" }
}

Write-Host "`nLog: ${sz}KB | Last write: $($mt.ToString('HH:mm:ss'))"
Write-Host "=== End ===" -ForegroundColor Cyan
