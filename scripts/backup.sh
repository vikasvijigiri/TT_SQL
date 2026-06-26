#!/usr/bin/env bash
# TT_SQL_PLATFORM - Backup learning.db + knowledge/
TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="database/backups/${TS}"
mkdir -p "${BACKUP_DIR}"
if [ -f "database/learning/learning.db" ]; then
  cp "database/learning/learning.db" "${BACKUP_DIR}/learning.db"
  echo "[OK] learning.db -> ${BACKUP_DIR}/"
fi
if [ -d "database/knowledge" ]; then
  cp -r "database/knowledge" "${BACKUP_DIR}/knowledge"
  echo "[OK] knowledge/ -> ${BACKUP_DIR}/"
fi
echo "Backup complete: ${BACKUP_DIR}"
