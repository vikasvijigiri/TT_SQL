#!/usr/bin/env bash
# TT_SQL_PLATFORM - Restart all services
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"${ROOT}/scripts/stop.sh"
sleep 2
"${ROOT}/scripts/start.sh"
