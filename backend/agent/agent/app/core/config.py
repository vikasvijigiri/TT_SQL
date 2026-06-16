import os
from pathlib import Path

# ── Root resolution ─────────────────────────────────────────────────────────
# BACKEND_DATA_DIR env var is the single source of truth for all runtime paths.
# In Docker:  set to /app/agent (matches the gateway's /data convention)
# Locally:    falls back to deriving from __file__ so `python -m agent.app.api`
#             works without any env setup.
_FILE_DERIVED = Path(__file__).resolve().parent.parent.parent.parent / "agent"
BACKEND_DIR = Path(os.environ.get("BACKEND_DATA_DIR", str(_FILE_DERIVED)))

# ── Source layout (code paths, never written at runtime) ─────────────────────
APP_DIR     = BACKEND_DIR / "app"
PROMPTS_DIR = APP_DIR / "prompts"
CONFIG_DIR  = BACKEND_DIR / "config"

# ── Resource paths (read-only data; large files excluded from Docker image) ──
RESOURCES_DIR = BACKEND_DIR / "resources"
DATABASES_DIR = RESOURCES_DIR / "databases"
DIALECTS_DIR  = RESOURCES_DIR / "dialects"
MEMORY_DIR    = RESOURCES_DIR / "memory"
LOGS_DIR      = RESOURCES_DIR / "logs"
GOLD_DIR      = RESOURCES_DIR / "gold"
INPUT_DIR     = RESOURCES_DIR / "input_data"

# ── Results paths (runtime-written; volume-mounted in Docker) ────────────────
RESULTS_DIR     = BACKEND_DIR / "results" / "evaluations"
DAB_RESULTS_DIR = RESULTS_DIR / "dab"

# ── DataAgentBench repo ───────────────────────────────────────────────────────
# Override with DAB_REPO env var (set in docker-compose and .env).
DAB_REPO = Path(os.environ.get("DAB_REPO", str(BACKEND_DIR.parent.parent.parent / "DataAgentBench")))


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_prompt_path(filename: str) -> str:
    return str(PROMPTS_DIR / filename)


def get_dialect_path(dialect: str) -> str:
    return str(DIALECTS_DIR / f"{dialect.lower()}.yaml")


def get_sqlite_db_path(db_name: str) -> str:
    return str(DATABASES_DIR / "sqlite" / f"{db_name.lower()}.sqlite")


def get_db_path(db_name: str, dialect: str = "snowflake") -> str:
    """Returns the root directory for a given DB and dialect."""
    db_root = DATABASES_DIR / dialect.lower() / db_name.upper()
    if not db_root.exists():
        db_root = DATABASES_DIR / dialect.lower() / db_name
        if not db_root.exists():
            raise ValueError(f"Database directory not found: {db_root}")
    return str(db_root)


def ensure_dirs() -> None:
    """Create all runtime-writable directories if they don't exist."""
    for d in [
        RESULTS_DIR,
        DAB_RESULTS_DIR,
        DAB_RESULTS_DIR / "_archive",
        LOGS_DIR,
        MEMORY_DIR,
        MEMORY_DIR / "dialects",
        MEMORY_DIR / "reasoning",
    ]:
        d.mkdir(parents=True, exist_ok=True)


ensure_dirs()
