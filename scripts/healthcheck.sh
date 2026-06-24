#!/usr/bin/env bash
# TT_SQL_PLATFORM - Health Check
# Usage: ./scripts/healthcheck.sh

check() {
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$2" 2>/dev/null)
  if [ "$code" = "200" ] || [ "$code" = "307" ]; then
    echo "[OK]   $1 -> $code"
  else
    echo "[FAIL] $1 -> ${code:-timeout}"
  fi
}

echo ""
echo "TT_SQL_PLATFORM Health Check"
echo "======================"
check "Backend"  "http://localhost:8000/health"
check "Gateway"  "http://localhost:8080/health"
check "Frontend" "http://localhost:3000"
check "API Docs" "http://localhost:8000/docs"
echo ""
