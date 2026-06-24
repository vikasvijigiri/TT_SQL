import os

from pathlib import Path

from dotenv import load_dotenv



load_dotenv()



# -- Backend code root (app code, prompts, config YAML - never written at runtime)

_FILE_DERIVED = Path(__file__).resolve().parent.parent.parent.parent / "agent"

BACKEND_DIR = Path(os.environ.get("BACKEND_DATA_DIR", str(_FILE_DERIVED)))



APP_DIR     = BACKEND_DIR / "app"

PROMPTS_DIR = APP_DIR / "prompts"

CONFIG_DIR  = BACKEND_DIR / "config"



# -- Database root (single source of truth for all runtime data) --------------

# Override with DATABASE_DIR env var (Docker: volume-mount a path here).

# Locally: defaults to <repo_root>/database/

_REPO_ROOT   = Path(__file__).resolve().parent.parent.parent.parent.parent.parent

DATABASE_DIR = Path(os.environ.get("DATABASE_DIR", str(_REPO_ROOT / "database")))



# -- Resources (read-only benchmark data) -------------------------------------

RESOURCES_DIR = DATABASE_DIR / "resources"



# Spider2 benchmark data

DATABASES_DIR = RESOURCES_DIR / "spider2" / "databases"

GOLD_DIR      = RESOURCES_DIR / "spider2" / "gold"

INPUT_DIR     = RESOURCES_DIR / "spider2" / "input"



# Shared cross-benchmark reference data

DIALECTS_DIR  = RESOURCES_DIR / "shared" / "dialects"

DOCUMENTS_DIR = RESOURCES_DIR / "shared" / "documents"



# -- Agent knowledge (learning state - written at runtime) --------------------

KNOWLEDGE_DIR = DATABASE_DIR / "knowledge"

MEMORY_DIR    = KNOWLEDGE_DIR           # alias kept for backward compatibility



# -- Logs ---------------------------------------------------------------------

LOGS_DIR = DATABASE_DIR / "logs" / "agent"



# -- Results (runtime-written trace files per run) ----------------------------

# Spider2 run results go directly under spider2/ (keyed by db_name)

RESULTS_DIR     = DATABASE_DIR / "results" / "spider2"

# DAB trace files are user-scoped: results/dab/{username}/

DAB_RESULTS_DIR = DATABASE_DIR / "results" / "dab"



# -- Canonical evaluation database --------------------------------------------

EVAL_DB = DATABASE_DIR / "evaluations" / "nquire.db"



# -- DataAgentBench repo -------------------------------------------------------

DAB_REPO = Path(os.environ.get("DAB_REPO", str(BACKEND_DIR.parent.parent.parent / "DataAgentBench")))



DEFAULT_USERNAME = os.environ.get("DEFAULT_USERNAME", "anonymous")





# -- Helpers ------------------------------------------------------------------



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





# -- Dynamic Run Directories --------------------------------------------------

def _get_run_context():

    """Helper to retrieve current run context from cache/environment."""

    username = DEFAULT_USERNAME

    run_id = "run_live"

    benchmark = "dab"

    

    try:

        from agent.services.cache import cache_service

        c_user = cache_service.get("shared_DAB_RUN_USERNAME")

        if c_user: username = c_user

        

        c_run = cache_service.get("shared_DAB_RUN_ID")

        if c_run: run_id = c_run

        

        c_bench = cache_service.get("shared_BENCHMARK")

        if c_bench: benchmark = c_bench

    except Exception:

        # Fallbacks for CLI or when cache is not running

        import sys

        dab_eval = sys.modules.get("agent.app.dab.dab_evaluator")

        if dab_eval:

            username = getattr(dab_eval, "DAB_RUN_USERNAME", username) or username

            run_id = getattr(dab_eval, "DAB_RUN_ID", run_id) or run_id

            

    return benchmark.lower(), username.lower(), run_id.lower()



def get_active_results_dir() -> "Path":

    bench, user, run = _get_run_context()

    import re

    safe_user = re.sub(r'[^a-z0-9_\-]', "", user) or "anonymous"

    safe_run = re.sub(r'[^a-z0-9_\-]', "", run) or "run_live"

    d = DATABASE_DIR / "results" / bench / safe_user / safe_run

    d.mkdir(parents=True, exist_ok=True)

    return d



def get_active_evals_dir() -> "Path":

    bench, user, run = _get_run_context()

    import re

    safe_user = re.sub(r'[^a-z0-9_\-]', "", user) or "anonymous"

    safe_run = re.sub(r'[^a-z0-9_\-]', "", run) or "run_live"

    d = DATABASE_DIR / "evaluations" / bench / safe_user / safe_run

    d.mkdir(parents=True, exist_ok=True)

    return d



def get_active_knowledge_dir() -> "Path":

    bench, user, run = _get_run_context()

    import re

    safe_user = re.sub(r'[^a-z0-9_\-]', "", user) or "anonymous"

    safe_run = re.sub(r'[^a-z0-9_\-]', "", run) or "run_live"

    d = DATABASE_DIR / "knowledge" / bench / safe_user / safe_run

    d.mkdir(parents=True, exist_ok=True)

    return d



def get_active_logs_dir() -> "Path":

    bench, user, run = _get_run_context()

    import re

    safe_user = re.sub(r'[^a-z0-9_\-]', "", user) or "anonymous"

    safe_run = re.sub(r'[^a-z0-9_\-]', "", run) or "run_live"

    d = DATABASE_DIR / "logs" / bench / safe_user / safe_run

    d.mkdir(parents=True, exist_ok=True)

    return d



def get_user_results_dir(username: str) -> "Path":

    # Deprecated fallback

    return get_active_results_dir()



def get_user_dab_results_dir(username: str) -> "Path":

    # Deprecated fallback

    return get_active_results_dir()



def get_user_dab_evals_dir(username: str) -> "Path":

    # Deprecated fallback

    return get_active_evals_dir()





def ensure_dirs(username: str = "") -> None:

    """Create all runtime-writable directories under database/ if they don't exist."""

    base_dirs = [

        EVAL_DB.parent,                         # database/evaluations/

        DATABASE_DIR / "submissions" / "dab",

        DATABASE_DIR / "submissions" / "spider2",

        DATABASE_DIR / "logs" / "api",

    ]

    for d in base_dirs:

        d.mkdir(parents=True, exist_ok=True)

    if username:

        get_active_results_dir()

        get_active_evals_dir()

        get_active_knowledge_dir()

        get_active_logs_dir()





ensure_dirs()

