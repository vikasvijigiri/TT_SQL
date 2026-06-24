#!/usr/bin/env bash
# TT_SQL_PLATFORM - Backup learning.db
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TS=$(date +%Y%m%d_%H%M%S)
SRC="${ROOT}/data/learning/learning.db"
DST="${ROOT}/data/learning/backups/learning_${TS}.db"
mkdir -p "$(dirname "${DST}")"
cp "${SRC}" "${DST}"
echo "[OK] Backup: ${DST}"
