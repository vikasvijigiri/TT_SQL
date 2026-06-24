#!/usr/bin/env bash
# TT_SQL_PLATFORM - Backup learning.db + knowledge/
TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="data/backups/${TS}"
mkdir -p "${BACKUP_DIR}"
if [ -f "data/learning/learning.db" ]; then
  cp "data/learning/learning.db" "${BACKUP_DIR}/learning.db"
  echo "[OK] learning.db -> ${BACKUP_DIR}/"
fi
if [ -d "data/knowledge" ]; then
  cp -r "data/knowledge" "${BACKUP_DIR}/knowledge"
  echo "[OK] knowledge/ -> ${BACKUP_DIR}/"
fi
echo "Backup complete: ${BACKUP_DIR}"
