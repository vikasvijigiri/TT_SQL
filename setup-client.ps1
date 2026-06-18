# ============================================================
#  NQuire Client Setup
#  Run this once on any laptop on the same Wi-Fi.
#  It adds the local DNS entry and opens the app in your browser.
#  No parameters needed — just double-click or right-click → Run with PowerShell.
# ============================================================

$ServerIP  = "172.16.17.18"
$hostname  = "dev.nquireai.com"
$appURL    = "http://dev.nquireai.com"
$hostsFile = "C:\Windows\System32\drivers\etc\hosts"

# ── Self-elevate to Administrator if not already ─────────────────────────────
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Requesting administrator privileges..." -ForegroundColor Yellow
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    Start-Process powershell -Verb RunAs -ArgumentList $argList
    exit
}

# ── Banner ────────────────────────────────────────────────────────────────────
Clear-Host
Write-Host ""
Write-Host "  ███╗   ██╗ ██████╗ ██╗   ██╗██╗██████╗ ███████╗" -ForegroundColor Cyan
Write-Host "  ████╗  ██║██╔═══██╗██║   ██║██║██╔══██╗██╔════╝" -ForegroundColor Cyan
Write-Host "  ██╔██╗ ██║██║   ██║██║   ██║██║██████╔╝█████╗  " -ForegroundColor Cyan
Write-Host "  ██║╚██╗██║██║▄▄ ██║██║   ██║██║██╔══██╗██╔══╝  " -ForegroundColor Cyan
Write-Host "  ██║ ╚████║╚██████╔╝╚██████╔╝██║██║  ██║███████╗" -ForegroundColor Cyan
Write-Host "  ╚═╝  ╚═══╝ ╚══▀▀═╝  ╚═════╝ ╚═╝╚═╝  ╚═╝╚══════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  NQuire AI — One-time Client Setup" -ForegroundColor White
Write-Host "  ─────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# ── Step 1: Update hosts file ─────────────────────────────────────────────────
Write-Host "  [1/3] Configuring local DNS entry..." -ForegroundColor Yellow

$content = Get-Content $hostsFile -Raw

# Remove any previous entries for this hostname or old domain
$content = $content -replace "(?m)^[^\n#]*\b(dev\.nquireai\.com|nquire\.local)\b[^\n]*\r?\n?", ""

# Append new entry
$entry   = "$ServerIP`t$hostname`t# NQuire AI (added by setup-client.ps1)"
$content = $content.TrimEnd() + "`r`n$entry`r`n"
Set-Content -Path $hostsFile -Value $content -Encoding ASCII

Write-Host "        Done! Mapped '$hostname' → $ServerIP" -ForegroundColor Green

# ── Step 2: Flush DNS cache ───────────────────────────────────────────────────
Write-Host ""
Write-Host "  [2/3] Flushing DNS cache..." -ForegroundColor Yellow
ipconfig /flushdns | Out-Null
Write-Host "        Done!" -ForegroundColor Green

# ── Step 3: Wait and open browser ────────────────────────────────────────────
Write-Host ""
Write-Host "  [3/3] Opening NQuire AI in your browser..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Start-Process $appURL
Write-Host "        Launched: $appURL" -ForegroundColor Green

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ─────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Setup complete! The app should now be open in your browser." -ForegroundColor Cyan
Write-Host "  You only need to run this script ONCE on this laptop." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Press any key to close this window..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
