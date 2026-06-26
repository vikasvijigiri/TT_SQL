#!/usr/bin/env bash
# TT_SQL_PLATFORM - Database migration runner
# Usage: ./scripts/migrate.sh [up|down|status]
set -e

ACTION=${1:-up}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MIGRATIONS_DIR="${ROOT}/database/migrations"

if [[ -z "${DATABASE_URL:-}" ]]; then
    # Construct from individual vars (matches .env convention)
    HOST="${DATABASE_HOST:-localhost}"
    PORT="${DATABASE_PORT:-5432}"
    NAME="${DATABASE_NAME:-ttsql}"
    USER="${DATABASE_USER:-ttsql}"
    PASS="${DATABASE_PASSWORD:-changeme}"
    DATABASE_URL="postgresql://${USER}:${PASS}@${HOST}:${PORT}/${NAME}"
fi

echo "==> Migration: ${ACTION} -- ${DATABASE_URL}"

if command -v alembic &>/dev/null; then
    cd "${ROOT}/services/agent-service"
    alembic "${ACTION}"
elif command -v flyway &>/dev/null; then
    flyway -url="jdbc:${DATABASE_URL}" -locations="filesystem:${MIGRATIONS_DIR}" "${ACTION}"
else
    echo "[INFO] No migration tool found -- applying SQL files directly"
    for f in "${MIGRATIONS_DIR}"/*.sql; do
        echo "  Applying: $(basename "${f}")"
        psql "${DATABASE_URL}" -f "${f}"
    done
fi

echo "[OK] Migration ${ACTION} complete"
