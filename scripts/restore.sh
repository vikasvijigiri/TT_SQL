#!/usr/bin/env bash
# TT_SQL_PLATFORM - Restore from backup
# Usage: ./scripts/restore.sh <backup-file.tar.gz>
set -e

BACKUP_FILE=${1:-""}
if [[ -z "${BACKUP_FILE}" ]]; then
    echo "Usage: ./scripts/restore.sh <backup-file.tar.gz>"
    exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${ROOT}/database"

echo "==> Restoring from: ${BACKUP_FILE}"
read -r -p "This will overwrite ${DATA_DIR}. Continue? [y/N] " confirm
[[ "${confirm}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

tar -xzf "${BACKUP_FILE}" -C "${ROOT}"
echo "[OK] Restore complete"
