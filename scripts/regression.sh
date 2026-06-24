#!/usr/bin/env bash
# TT_SQL_PLATFORM - Regression Test Runner
# Usage: ./scripts/regression.sh [prompt|validator|sql|all]
MODE=${1:-all}
cd services/agent-service
case $MODE in
  prompt)    python -m pytest tests/regression/ -k "prompt" -v ;;
  validator) python -m pytest tests/regression/ -k "validator" -v ;;
  sql)       python -m pytest tests/regression/ -k "sql" -v ;;
  *)         python -m pytest tests/regression/ tests/benchmark/ -v ;;
esac
