#!/usr/bin/env bash
# TT_SQL_V4 - Single command startup
# Usage: ./scripts/start.sh
set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT=8000
GATEWAY_PORT=8080
FRONTEND_PORT=3000

GREEN="\033[0;32m"
CYAN="\033[0;36m"
RESET="\033[0m"

banner() { echo -e "${CYAN}\n==> $1${RESET}"; }
ok()     { echo -e "${GREEN}[OK] $1${RESET}"; }

check_health() {
  local port=$1 name=$2
  if curl -s --max-time 3 "http://localhost:${port}/health" > /dev/null 2>&1; then
    ok "${name} healthy at :${port}"
  else
    echo "  [WARN] ${name} not yet responding at :${port}"
  fi
}

# 1. Gateway (Go)
banner "Starting Gateway on :${GATEWAY_PORT}"
cd "${ROOT_DIR}/services/gateway"
if [ -f "gateway.exe" ]; then
  ./gateway.exe &
elif command -v go &>/dev/null; then
  go run ./cmd/server/main.go &
else
  echo "  [SKIP] Go not installed"
fi
GATEWAY_PID=$!

# 2. Backend (Python)
banner "Starting Backend on :${BACKEND_PORT}"
cd "${ROOT_DIR}/services/agent-service"
uvicorn main:app --host 0.0.0.0 --port "${BACKEND_PORT}" --reload &
BACKEND_PID=$!

# 3. Frontend (npm)
banner "Starting Frontend on :${FRONTEND_PORT}"
cd "${ROOT_DIR}/apps/web"
npm run dev &
FRONTEND_PID=$!

# 4. Health checks
banner "Waiting for services..."
sleep 6
check_health "${BACKEND_PORT}"  "Backend"
check_health "${GATEWAY_PORT}"  "Gateway"
check_health "${FRONTEND_PORT}" "Frontend"

# 5. Print URLs
echo ""
echo -e "${GREEN}========================================"
echo "  TT_SQL_PLATFORM RUNNING"
echo "========================================"
echo "  Frontend : http://localhost:${FRONTEND_PORT}"
echo "  Gateway  : http://localhost:${GATEWAY_PORT}"
echo "  Backend  : http://localhost:${BACKEND_PORT}"
echo "  Docs     : http://localhost:${BACKEND_PORT}/docs"
echo -e "========================================${RESET}"
echo ""
echo "PIDs: Gateway=${GATEWAY_PID}  Backend=${BACKEND_PID}  Frontend=${FRONTEND_PID}"
echo "Stop: ./scripts/stop.sh"
wait
