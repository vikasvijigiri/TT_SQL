#Requires -RunAsAdministrator
# Run this script as Administrator on the server machine

$serverName = "nquire"
$port = 80

Write-Host "=== nquire Local Server Setup ===" -ForegroundColor Cyan
Write-Host ""

# 1. Open firewall port 80
Write-Host "[1/3] Opening port $port in Windows Firewall..." -ForegroundColor Yellow
$existingRule = Get-NetFirewallRule -DisplayName "nquire HTTP (port $port)" -ErrorAction SilentlyContinue
if ($existingRule) {
    Write-Host "      Firewall rule already exists." -ForegroundColor Green
} else {
    New-NetFirewallRule -DisplayName "nquire HTTP (port $port)" `
        -Direction Inbound -Protocol TCP -LocalPort $port `
        -Action Allow -Profile Any | Out-Null
    Write-Host "      Firewall rule created." -ForegroundColor Green
}

# 2. Get network IP
Write-Host ""
Write-Host "[2/3] Server IP addresses:" -ForegroundColor Yellow
$ips = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.InterfaceAlias -notmatch 'Loopback|vEthernet|McAfee|Bluetooth|Local Area' } |
    Select-Object InterfaceAlias, IPAddress
$ips | Format-Table -AutoSize
$primaryIP = $ips | Select-Object -First 1 -ExpandProperty IPAddress
Write-Host "      Primary IP: $primaryIP" -ForegroundColor Green

# 3. Rename PC (enables mDNS so clients resolve nquire.local automatically)
Write-Host ""
Write-Host "[3/3] PC Rename for mDNS..." -ForegroundColor Yellow
$currentName = $env:COMPUTERNAME
if ($currentName -eq $serverName) {
    Write-Host "      PC is already named '$serverName' — mDNS will work automatically." -ForegroundColor Green
} else {
    Write-Host "      Current PC name: $currentName"
    Write-Host "      To enable 'http://nquire.local' for ALL clients automatically (no client config),"
    Write-Host "      the PC needs to be renamed to '$serverName'. This requires a restart."
    $answer = Read-Host "      Rename PC to '$serverName' now? (y/N)"
    if ($answer -match '^[Yy]') {
        Rename-Computer -NewName $serverName -Force
        Write-Host ""
        Write-Host "      PC renamed. A restart is required." -ForegroundColor Yellow
        $restart = Read-Host "      Restart now? (y/N)"
        if ($restart -match '^[Yy]') {
            Restart-Computer -Force
        } else {
            Write-Host "      Remember to restart before testing!" -ForegroundColor Yellow
        }
    } else {
        Write-Host ""
        Write-Host "      SKIPPED rename. Clients must use the hosts file instead." -ForegroundColor Yellow
        Write-Host "      Share this with each client to add to their hosts file:" -ForegroundColor Cyan
        Write-Host "        $primaryIP    nquire.local" -ForegroundColor White
        Write-Host ""
        Write-Host "      Or run 'setup-client.ps1' as Administrator on each client PC." -ForegroundColor Cyan
    }
}

Write-Host ""
Write-Host "=== Server setup complete ===" -ForegroundColor Cyan
Write-Host "Start the app with:  docker-compose up -d" -ForegroundColor White
Write-Host "App will be at:      http://nquire.local" -ForegroundColor White
