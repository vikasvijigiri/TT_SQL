#!/usr/bin/env bash
# TT_SQL_PLATFORM - Load test runner
# Usage: ./scripts/loadtest.sh [--url URL] [--rps 50] [--duration 60s]
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
URL=${LOADTEST_URL:-"http://localhost:80"}
RPS=${LOADTEST_RPS:-50}
DURATION=${LOADTEST_DURATION:-60s}

echo "==> Load test: ${URL} @ ${RPS} rps for ${DURATION}"

if command -v k6 &>/dev/null; then
    k6 run --vus "${RPS}" --duration "${DURATION}" "${ROOT}/tests/load/main.js"
elif command -v locust &>/dev/null; then
    locust -f "${ROOT}/tests/load/locustfile.py" --headless -u "${RPS}" --run-time "${DURATION}" --host "${URL}"
else
    echo "[SKIP] No load test runner found (install k6 or locust)"
    exit 1
fi
