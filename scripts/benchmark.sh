#!/usr/bin/env bash
# TT_SQL_V4 - Run benchmarks
# Usage: ./scripts/benchmark.sh [bird|dab|spider2]
BENCH=${1:-bird}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}/services/agent-service"
python -m pytest "tests/benchmark/" -k "${BENCH}" -v
