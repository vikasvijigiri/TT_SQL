# start.ps1 — Launch all NQuire services (Docker DBs + native app services)
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  NQuire — Full Stack Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Docker: Postgres + Redis ───────────────────────────────────────────────
Write-Host "[1/4] Starting Docker services (Postgres + Redis)..." -ForegroundColor Yellow

$composeFile = "$ROOT\docker-compose.db.yml"
if (-not (Test-Path $composeFile)) {
    Write-Host "  ERROR: docker-compose.db.yml not found at $ROOT" -ForegroundColor Red
    exit 1
}

# Check Docker daemon is running
$dockerOk = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch {}

if (-not $dockerOk) {
    Write-Host "  ERROR: Docker daemon is not running. Start Docker Desktop first." -ForegroundColor Red
    exit 1
}

docker compose -f "$composeFile" up -d 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: docker compose failed. Check docker-compose.db.yml." -ForegroundColor Red
    exit 1
}

# Wait for Postgres to be healthy (up to 30s)
Write-Host "  Waiting for Postgres to be ready..." -ForegroundColor DarkGray
$pgReady = $false
for ($i = 0; $i -lt 15; $i++) {
    $result = docker compose -f "$composeFile" ps postgres 2>&1 | Select-String "healthy"
    if ($result) { $pgReady = $true; break }
    Start-Sleep -Seconds 2
}
if ($pgReady) {
    Write-Host "  Postgres: READY" -ForegroundColor Green
} else {
    Write-Host "  Postgres: still starting (continuing anyway)" -ForegroundColor Yellow
}

# Wait for Redis to be healthy (up to 20s)
Write-Host "  Waiting for Redis to be ready..." -ForegroundColor DarkGray
$redisReady = $false
for ($i = 0; $i -lt 10; $i++) {
    $result = docker compose -f "$composeFile" ps redis 2>&1 | Select-String "healthy"
    if ($result) { $redisReady = $true; break }
    Start-Sleep -Seconds 2
}
if ($redisReady) {
    Write-Host "  Redis:    READY" -ForegroundColor Green
} else {
    Write-Host "  Redis:    still starting (continuing anyway)" -ForegroundColor Yellow
}

Write-Host ""

# ── 2. Python Agent (FastAPI :8010) ──────────────────────────────────────────
Write-Host "[2/4] Launching Python Agent (:8010)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
  Set-Location '$ROOT\backend\agent'
  Write-Host '=== NQuire Agent (Python :8010) ===' -ForegroundColor Cyan
  python -m uvicorn agent.app.api:app --host 0.0.0.0 --port 8010 --workers 4
"@

# ── 3. Go Gateway (:8002) ────────────────────────────────────────────────────
Write-Host "[3/4] Launching Go Gateway (:8002)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
  Set-Location '$ROOT\backend\gateway'
  Write-Host '=== NQuire Gateway (Go :8002) ===' -ForegroundColor Green
  .\gateway.exe
"@

# ── 4. React Frontend (Vite :5173) ───────────────────────────────────────────
Write-Host "[4/4] Launching React Frontend (:5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
  Set-Location '$ROOT\frontend'
  Write-Host '=== NQuire Frontend (Vite :5173) ===' -ForegroundColor Magenta
  npm run dev
"@

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  All services launching..." -ForegroundColor Green
Write-Host ""
Write-Host "  App URL  : http://localhost:5173" -ForegroundColor Cyan
Write-Host "  API URL  : http://localhost:8010" -ForegroundColor Cyan
Write-Host "  Postgres : localhost:5432" -ForegroundColor DarkGray
Write-Host "  Redis    : localhost:6379" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Wait ~10s for Python agent to initialize." -ForegroundColor DarkGray
Write-Host "  Then open the DAB Studio tab and click Run All." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
