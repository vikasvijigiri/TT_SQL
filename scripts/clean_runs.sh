#!/usr/bin/env bash
# TT_SQL_PLATFORM - Remove old run artifacts (keep last N)
KEEP=${1:-50}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNS="${ROOT}/data/runs"
ls -dt "${RUNS}"/run_*/ 2>/dev/null | tail -n +"$((KEEP+1))" | xargs rm -rf
echo "[OK] Kept last ${KEEP} runs"
