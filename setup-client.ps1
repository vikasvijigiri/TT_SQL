# Usage: .\setup-client.ps1 -ServerIP 172.16.17.18

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerIP
)

# Self-elevate if not already running as admin
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $args = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -ServerIP `"$ServerIP`""
    Start-Process powershell -Verb RunAs -ArgumentList $args
    exit
}

$hostname = "nquire.local"
$hostsFile = "C:\Windows\System32\drivers\etc\hosts"
$entry = "$ServerIP`t$hostname"

Write-Host "=== nquire Client Setup ===" -ForegroundColor Cyan
Write-Host "Adding '$hostname -> $ServerIP' to hosts file..."

$content = Get-Content $hostsFile -Raw

# Remove any existing entry for nquire.local
$content = $content -replace "(?m)^[^\n#]*\bnquire\.local\b[^\n]*\n?", ""

# Append new entry
$content = $content.TrimEnd() + "`r`n$entry`r`n"
Set-Content -Path $hostsFile -Value $content -Encoding ASCII

Write-Host "Done! Try opening http://nquire.local in your browser." -ForegroundColor Green
