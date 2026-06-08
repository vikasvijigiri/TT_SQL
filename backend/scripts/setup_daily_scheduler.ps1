# setup_daily_scheduler.ps1
# --------------------------
# Registers a Windows Task Scheduler job that runs the self-improving pipeline
# daily at 02:07 AM.
#
# Run once as Administrator:
#   powershell -ExecutionPolicy Bypass -File backend\scripts\setup_daily_scheduler.ps1

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonExe   = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe) {
    Write-Error "Python not found on PATH. Install Python and re-run."
    exit 1
}

$scriptPath  = Join-Path $projectRoot "backend\scripts\run_self_improve.py"
$logPath     = Join-Path $projectRoot "backend\resources\logs\self_improve_scheduler.log"
$taskName    = "TT_SQL_V2_SelfImprove"

# Build the action: python script.py >> log.log 2>&1
$action  = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "`"$scriptPath`" >> `"$logPath`" 2>&1" `
    -WorkingDirectory $projectRoot

$trigger = New-ScheduledTaskTrigger -Daily -At "02:07AM"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 8) `
    -RestartCount 1 `
    -RestartInterval (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false

$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType S4U `
    -RunLevel Highest

# Remove existing task if present
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName  $taskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Description "Runs TT_SQL_V2 daily self-improving pipeline (max 3 rounds)"

Write-Host ""
Write-Host "Task '$taskName' registered successfully."
Write-Host "  Python   : $pythonExe"
Write-Host "  Script   : $scriptPath"
Write-Host "  Schedule : Daily at 02:07 AM"
Write-Host "  Log      : $logPath"
Write-Host ""
Write-Host "To verify: Get-ScheduledTask -TaskName '$taskName'"
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
