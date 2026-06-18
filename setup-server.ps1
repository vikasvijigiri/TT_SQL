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

# 3. DNS / Local Access setup
Write-Host ""
Write-Host "[3/3] Local Access & DNS Setup Info:" -ForegroundColor Yellow
Write-Host "      To enable users to access the app via http://dev.nquireai.com, you can either:"
Write-Host ""
Write-Host "      A) Configure a local DNS server (e.g. Technitium DNS):" -ForegroundColor Cyan
Write-Host "         - Create a zone for 'dev.nquireai.com' pointing to '$primaryIP'"
Write-Host "         - Set your Wi-Fi router's DHCP DNS server to Technitium's IP"
Write-Host "         - No client configuration is required!"
Write-Host ""
Write-Host "      B) Use client-side hosts file fallback:" -ForegroundColor Cyan
Write-Host "         - Run 'setup-client.ps1 -ServerIP $primaryIP' as Administrator on client PCs"
Write-Host "         - Or add this line manually to C:\Windows\System32\drivers\etc\hosts:"
Write-Host "           $primaryIP    dev.nquireai.com" -ForegroundColor White
Write-Host ""

Write-Host ""
Write-Host "=== Server setup complete ===" -ForegroundColor Cyan
Write-Host "Start the app with:  docker-compose up -d" -ForegroundColor White
Write-Host "App will be at:      http://dev.nquireai.com" -ForegroundColor White
