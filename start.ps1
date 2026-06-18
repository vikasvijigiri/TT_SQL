# start.ps1 — Launch all NQuire services natively (DBs already in Docker via docker-compose.db.yml)
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Python Agent (FastAPI on :8010)
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
  Set-Location '$ROOT\backend\agent'
  Write-Host '=== NQuire Agent (Python :8010) ===' -ForegroundColor Cyan
  python -m uvicorn agent.app.api:app --host 0.0.0.0 --port 8010 --workers 4
"@

# 2. Go Gateway (:8002)
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
  Set-Location '$ROOT\backend\gateway'
  Write-Host '=== NQuire Gateway (Go :8002) ===' -ForegroundColor Green
  .\gateway.exe
"@

# 3. React Frontend (Vite dev :3000)
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
  Set-Location '$ROOT\frontend'
  Write-Host '=== NQuire Frontend (Vite :3000) ===' -ForegroundColor Magenta
  npm run dev
"@

Write-Host ""
Write-Host "All services launching in separate windows." -ForegroundColor Yellow
Write-Host "App URL: http://localhost:5173" -ForegroundColor Yellow
Write-Host "(wait ~5s for all services to start)" -ForegroundColor DarkGray
