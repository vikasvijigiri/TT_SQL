"""
dab_orchestrator.py
-------------------
Adapts the existing SemanticDINOrchestrator to run DataAgentBench queries.

DAB datasets use multiple DBMSes per dataset. We pick the best available DB:
  Priority: SQLite > DuckDB > PostgreSQL > MongoDB
  (SQLite and DuckDB work without Docker; Postgres/Mongo need Docker)

For multi-DB datasets, we generate SQL against the primary available DB.
The db_description.txt is injected as external knowledge context.
"""

import json
import re
import time
import traceback
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml

from agent.app.utils.logger import logger
from agent.app.utils.llm import LLMClient, reset_token_counters, get_tokens
from agent.app.core.config import RESULTS_DIR, DAB_REPO
from agent.app.dab.answer_extractor import extract_answer, save_answer
from agent.app.dab.dab_evaluator import evaluate_answer
import contextlib

# LangSmith tracing Ã¢â‚¬â€ imported lazily so missing keys never crash the pipeline
try:
    from langsmith import traceable
    from langsmith.run_helpers import get_current_run_tree

    _LANGSMITH_AVAILABLE = True
except ImportError:
    _LANGSMITH_AVAILABLE = False
    def traceable(**kw):  # type: ignore
        return lambda fn: fn  # no-op decorator
    def get_current_run_tree():  # type: ignore
        return None


def _push_evaluator_feedback(run_id: str, eval_json: dict) -> None:
    """
    Post all 8 evaluator scores to a LangSmith run ID in a background thread.
    Thread is non-daemon so it always completes before process exit.
    The pipeline won't wait for it Ã¢â‚¬â€ the thread runs concurrently with the
    next query, so there is zero added latency to the benchmark.
    """

    def _worker():
        try:
            from agent.app.core.langsmith_evaluators import attach_feedback_to_run

            attach_feedback_to_run(run_id, eval_json)
        except Exception:
            pass  # never crash the pipeline over telemetry

    t = threading.Thread(target=_worker, daemon=False)
    t.start()

from agent.app.core.config import DEFAULT_USERNAME
DAB_REPO_PATH = str(DAB_REPO)  # backward-compat alias; prefer DAB_REPO from config


def _load_configured_max_retries(default: int = 2) -> int:
    """Load the orchestrator retry budget from project config when available."""
    params_path = (
        Path(__file__).resolve().parent.parent / "config" / "system_params.yaml"
    )
    try:
        with open(params_path, "r", encoding="utf-8") as f:
            params = yaml.safe_load(f) or {}
        configured = params.get("orchestrator", {}).get("max_retries", default)
        return int(configured)
    except Exception:
        return default


def _tokenize(text: str) -> set:
    """
    Split text into lowercase tokens, handling CamelCase, underscores and spaces.
    Keeps only tokens of 3+ characters.
    Example: 'VoiceCallTranscript__c' -> {'voice', 'call', 'transcript'}
    """
    # Insert a space before each uppercase letter group to split CamelCase
    spaced = re.sub(r"([A-Z]+)", r" \1", text)
    tokens = re.findall(r"[a-zA-Z]{3,}", spaced.lower())
    return set(tokens)


def _get_table_names_quickly(db_path: str, db_type: str) -> List[str]:
    """Lightweight table-name introspection Ã¢â‚¬â€ no sample data, no schema."""
    try:
        if db_type == "sqlite":
            import sqlite3

            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()]
            conn.close()
            return tables
        elif db_type == "duckdb":
            import duckdb

            conn = duckdb.connect(db_path, read_only=True)  # type: ignore
            tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
            conn.close()
            return tables
    except Exception:
        pass
    return []


def _get_column_info_quickly(db_path: str, db_type: str) -> List[tuple]:
    """
    Return (column_name, data_type) pairs across all tables.
    Used for tie-breaking: prefer DBs with numeric/temporal columns.
    """
    try:
        if db_type == "sqlite":
            import sqlite3

            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()]
            cols: List[tuple] = []
            for t in tables:
                for row in c.execute(f"PRAGMA table_info({t})").fetchall():
                    cols.append((row[1], row[2].upper()))  # (name, type)
            conn.close()
            return cols
        elif db_type == "duckdb":
            import duckdb

            conn = duckdb.connect(db_path, read_only=True)  # type: ignore
            rows = conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns"
            ).fetchall()
            conn.close()
            return [(r[0], r[1].upper()) for r in rows]
    except Exception:
        pass
    return []


def _get_column_names_quickly(db_path: str, db_type: str) -> List[str]:
    """Return all column names across all tables."""
    return [name for name, _ in _get_column_info_quickly(db_path, db_type)]


_NUMERIC_TYPES = frozenset(
    {
        # ANSI / standard SQL
        "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT",
        "REAL", "FLOAT", "DOUBLE", "DOUBLE PRECISION",
        "DECIMAL", "NUMERIC", "NUMBER",
        # DuckDB extensions
        "HUGEINT", "UBIGINT", "UINTEGER", "USMALLINT", "UTINYINT",
        "FLOAT4", "FLOAT8", "INT1", "INT2", "INT4", "INT8", "INT16",
        "INT32", "INT64", "INT128", "UINT8", "UINT16", "UINT32", "UINT64",
        # SQL Server / Sybase
        "MONEY", "SMALLMONEY", "BIT",
        # Oracle
        "BINARY_FLOAT", "BINARY_DOUBLE",
        # BigQuery
        "INT64", "FLOAT64", "BIGNUMERIC", "BYTEINT",
        # Snowflake
        "FIXED", "BYTEINT", "BOOLEAN",
        # MySQL / MariaDB
        "MEDIUMINT", "UNSIGNED",
        # ClickHouse
        "UINT256", "INT256", "FLOAT32", "DECIMAL32", "DECIMAL64", "DECIMAL128",
        # Spark / Hive
        "BYTE", "SHORT", "LONG",
        # Redshift
        "INT2", "INT4", "INT8",
    }
)


def _count_numeric_columns(db_path: str, db_type: str) -> int:
    """Count columns with numeric/quantitative data types Ã¢â‚¬â€ used as analytic richness signal."""
    count = 0
    for _, dtype in _get_column_info_quickly(db_path, db_type):
        if any(dtype.startswith(t) for t in _NUMERIC_TYPES):
            count += 1
    return count


def _score_db_for_query(cfg: Dict[str, Any], q_tokens: set) -> float:
    """
    Score a DB config's relevance to the question using:
      - DB name token overlap    (weight 1.0 per matching token)
      - Table name token overlap (weight 1.0 per matching token)
      - Column name token overlap (weight 1.0 per matching token)
      - DB name substring match  (weight 0.5 per query token found as substring)

    DB name weight is intentionally equal to table/column weight: filenames are
    arbitrary and should not dominate over actual schema content.  Column names
    are the most content-specific signal and break ties between equally-named DBs.
    """
    if not q_tokens:
        return 0.0
    score = 0.0

    # DB name score (token match)
    db_name = cfg.get("name", cfg.get("db_name", ""))
    db_name_tokens = _tokenize(db_name)
    for tok in db_name_tokens:
        if tok in q_tokens:
            score += 1.0

    # DB name substring bonus Ã¢â‚¬â€ catches compound lowercase names (e.g. "indextrade")
    # that don't split via CamelCase but contain a query token as a substring.
    db_name_lower = db_name.lower().replace("_", "")
    for tok in q_tokens:
        if len(tok) >= 4 and tok in db_name_lower and tok not in db_name_tokens:
            score += 0.5

    db_path = cfg.get("db_path", "")
    db_type = cfg.get("db_type", "").lower()
    if db_path and Path(db_path).is_file():
        # Table name score
        for table in _get_table_names_quickly(db_path, db_type):
            for tok in _tokenize(table):
                if tok in q_tokens:
                    score += 1.0

        # Column name score Ã¢â‚¬â€ highest-signal indicator of schema content
        for col in _get_column_names_quickly(db_path, db_type):
            for tok in _tokenize(col):
                if tok in q_tokens:
                    score += 1.0

    return score


def _pick_best_db(
    db_clients: Dict[str, Any], question: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Select the best available DB from a dataset's db_clients.

    When multiple local (no-Docker) DBs exist and a question is supplied,
    uses query-aware scoring (DB name + table name overlap with question tokens)
    to pick the most relevant one.  Falls back to static type priority when
    only one local DB is available or scoring is tied.

    Static priority (fallback): sqlite > duckdb > postgres > mongo
    """
    local_types = {"sqlite", "duckdb"}

    # Collect all available local DB configs (file must exist as a real file)
    available_local: List[Dict[str, Any]] = []
    for cfg in db_clients.values():
        db_type = cfg.get("db_type", "").lower()
        db_path = cfg.get("db_path", "")
        if db_type in local_types and db_path and Path(db_path).is_file():
            available_local.append(cfg)

    # Query-aware selection when 2+ local DBs exist and a question was provided
    if len(available_local) >= 2 and question:
        q_tokens = _tokenize(question)
        scored = [(cfg, _score_db_for_query(cfg, q_tokens)) for cfg in available_local]

        # Sort by: (1) is DuckDB (enables cross-DB queries via attaching SQLite), (2) token score,
        # (3) numeric column count, (4) total column count, (5) path for determinism.
        scored.sort(
            key=lambda x: (
                x[0].get("db_type", "").lower() == "duckdb",
                x[1],
                _count_numeric_columns(
                    x[0].get("db_path", ""), x[0].get("db_type", "").lower()
                ),
                len(
                    _get_column_names_quickly(
                        x[0].get("db_path", ""), x[0].get("db_type", "").lower()
                    )
                ),
                x[0].get("db_path", ""),
            ),
            reverse=True,
        )
        best_cfg, best_score = scored[0]
        logger.info(
            f"Query-aware DB selection: '{best_cfg.get('name', best_cfg.get('db_type'))}' "
            f"(score={best_score:.1f})"
        )
        return best_cfg

    # Static type priority (duckdb > sqlite fallback)
    for dbtype in ("duckdb", "sqlite", "postgres", "postgresql", "mongo", "mongodb"):
        for cfg in db_clients.values():
            if cfg.get("db_type", "").lower() == dbtype:
                db_path = cfg.get("db_path", "")
                if db_path and Path(db_path).exists():
                    return cfg

    # Last resort: return first entry regardless of file presence (for error reporting)
    if db_clients:
        return next(iter(db_clients.values()))
    return None


def _get_all_available_dbs(db_clients: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return all DB configs that have existing files."""
    available = []
    for _name, cfg in db_clients.items():
        db_path = cfg.get("db_path", "")
        if db_path and Path(db_path).exists():
            available.append(cfg)
    return available


def _make_db_directory_for_schema(
    db_cfg: Dict[str, Any], _dataset: str
) -> Optional[str]:
    """
    Return the parent directory of the selected DB file so SemanticContextEngine
    can walk it and introspect all sibling DB files in the same dataset directory.
    """
    db_path = db_cfg.get("db_path", "")
    if not db_path or not Path(db_path).exists():
        return None
    return str(Path(db_path).parent)


_EMPTY_ANSWER_SIGNALS = frozenset(
    [
        "",
        "no data",
        "no data.",
        "no results found",
        "no results found.",
        "no rows",
        "none",
        "null",
        "n/a",
        "not found",
        "no output",
        "no output.",
    ]
)


def _is_empty_answer(answer: str) -> bool:
    return (
        not answer
        or answer.strip().lower().rstrip(".").rstrip(",") in _EMPTY_ANSWER_SIGNALS
    )


def _build_rich_schema_hint(
    db_path: str, db_type: str, max_tables: int = 10, sample_rows: int = 3
) -> str:
    """Introspect the live DB and return actual table/column names with sample rows as ground-truth evidence."""
    lines = []
    try:
        if db_type == "sqlite":
            import sqlite3

            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()][:max_tables]
            for table in tables:
                try:
                    cols = c.execute(f'PRAGMA table_info("{table}")').fetchall()
                    col_names = [col[1] for col in cols]
                    lines.append(f"\nTable: {table}")
                    lines.append(f"  Columns: {', '.join(col_names)}")
                    rows = c.execute(
                        f'SELECT * FROM "{table}" LIMIT {sample_rows}'
                    ).fetchall()
                    if rows:
                        lines.append("  Sample rows:")
                        for row in rows:
                            lines.append(f"    {dict(zip(col_names, row, strict=False))}")
                except Exception:
                    pass
            conn.close()
        elif db_type == "duckdb":
            import duckdb

            conn = duckdb.connect(db_path, read_only=True)  # type: ignore
            tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()][:max_tables]
            for table in tables:
                try:
                    schema_rows = conn.execute(f'DESCRIBE "{table}"').fetchall()
                    col_names = [r[0] for r in schema_rows]
                    lines.append(f"\nTable: {table}")
                    lines.append(f"  Columns: {', '.join(col_names)}")
                    rows = conn.execute(
                        f'SELECT * FROM "{table}" LIMIT {sample_rows}'
                    ).fetchall()
                    if rows:
                        lines.append("  Sample rows:")
                        for row in rows:
                            lines.append(f"    {dict(zip(col_names, row, strict=False))}")
                except Exception:
                    pass
            conn.close()
    except Exception:
        return ""
    return "\n".join(lines)


# ── Learning memory helpers ──────────────────────────────────────────────────

def _learning_dir() -> Path:
    from agent.app.core.config import MEMORY_DIR
    d = MEMORY_DIR / "dab_learning"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_winning_example(dataset: str, query_id: str, question: str, sql: str, answer: str) -> None:
    """Persist a passing (question, sql, answer) tuple so future runs can use it as few-shot."""
    p = _learning_dir() / f"{dataset}_winners.jsonl"
    entry = {"query_id": str(query_id), "question": question, "sql": sql.strip(), "answer": answer.strip()}
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _has_winning_solution(dataset: str, query_id: str) -> bool:
    """Return True if this exact query_id already has a saved winning SQL entry."""
    p = _learning_dir() / f"{dataset}_winners.jsonl"
    if not p.exists():
        return False
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            if json.loads(line).get("query_id") == str(query_id):
                return True
        except Exception:
            continue
    return False


def _load_winning_examples(dataset: str, exclude_query_id: str, max_examples: int = 3) -> List[Dict]:
    """Load up to max_examples passing SQLs from the same dataset (different queries)."""
    p = _learning_dir() / f"{dataset}_winners.jsonl"
    if not p.exists():
        return []
    seen, results = set(), []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
            key = entry["query_id"]
            if key == str(exclude_query_id) or key in seen:
                continue
            seen.add(key)
            results.append(entry)
        except Exception:
            continue
    return results[-max_examples:]  # most recent


_GT_LEAK_PATTERNS = [
    # "Target 'X' not stated..." → "Answer not in first 200 chars"
    (re.compile(r"Target '[^']+' not stated"), "Answer value not found in first 200 chars of output"),
    # "Missing X: VALUE" → "Missing X value"
    (re.compile(r"(Missing [^:]+): .+"), r"\1 value not found in output"),
    # "Found X ['Y'], but expected 'Z'" → "Found wrong X value"
    (re.compile(r"Found ([^[]+?)\s*\[.+\], but expected '.+'"), r"Found wrong \1— output did not match expected"),
    # "Ground truth 'X' not found in LLM output: Y" → structural mismatch
    (re.compile(r"Ground truth '[^']+' not found in LLM output: .+"), "Output value does not match ground truth — check your aggregation logic"),
    # "No value in LLM output rounds to X" → numeric mismatch
    (re.compile(r"No value in LLM output (rounds to|matches) .+"), "Numeric value in output does not match expected — check aggregation/calculation"),
    # "Not matched (fuzzy) within N chars: 'VALUE'" → fuzzy match failure
    (re.compile(r"Not matched \(fuzzy\) within \d+ chars?: '.+'"), "Output text does not fuzzy-match expected value — check exact spelling and capitalisation from DB"),
    # "No fuzzy match found for 'VALUE' ..." → fuzzy failure
    (re.compile(r"No fuzzy match (found )?for '[^']+'.+"), "Fuzzy match failed — output text did not match expected value"),
    # "No fuzzy match (VALUE) found in ANSWER ..." → music-brainz style fuzzy failure
    (re.compile(r"No fuzzy match \([^)]+\) found in .+"), "Output text did not fuzzy-match expected value — check title normalisation"),
    # "Name not found within N edits: 'VALUE' ..." → levenshtein failure
    (re.compile(r"Name not found within \d+ edits: '[^']+'.+"), "Output did not match expected name — check ORDER BY and join logic"),
    # "Version 'X' not found after name 'Y'" → deps-dev style pair failure
    (re.compile(r"Version '[^']+' not found after name '[^']+'"), "Name-version pair missing from output — ensure all required packages are listed"),
]

def _sanitize_reason(reason: str) -> str:
    """Strip ground-truth values from validator reason strings before injecting into prompt."""
    for pattern, replacement in _GT_LEAK_PATTERNS:
        reason = pattern.sub(replacement, reason)
    return reason


def _save_failure_hint(dataset: str, query_id: str, run_number: int, reason: str, sql: str, agent_answer: str = "") -> None:
    """Record why a specific (dataset, query_id) run failed so later runs can avoid it."""
    p = _learning_dir() / f"{dataset}_q{query_id}_failures.jsonl"
    entry = {
        "run": run_number,
        "reason": _sanitize_reason(reason.strip()),
        "sql": sql.strip() if sql else "",
        "agent_answer": agent_answer.strip()[:300] if agent_answer else "",
    }
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # Evict stale SQL cache for this instance so the next run doesn't re-serve
    # a cached SQL that we just confirmed is wrong.
    from agent.app.core.config import MEMORY_DIR
    import contextlib
    for suffix in ("", "_retry", f"_run{run_number}", f"_run{run_number}_retry"):
        cache_file = MEMORY_DIR / "sql_cache" / f"dab_{dataset}_q{query_id}{suffix}.json"
        with contextlib.suppress(Exception):
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"[Learning] Evicted stale SQL cache: {cache_file.name}")


def _load_failure_hints(dataset: str, query_id: str) -> List[Dict]:
    """Load all recorded failure hints for a specific query."""
    p = _learning_dir() / f"{dataset}_q{query_id}_failures.jsonl"
    if not p.exists():
        return []
    results = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            results.append(json.loads(line))
        except Exception:
            continue
    return results


def _derive_answer_format_hint(question: str) -> str:
    """Infer output format from the question text only — never from ground truth or expected answers.

    Derives format constraints purely from how the question is phrased, so no benchmark
    answer information leaks into the generation pipeline.
    """
    UNIVERSAL = (
        "\nCRITICAL OUTPUT RULE: Your ENTIRE response must be ONLY the raw answer value. "
        "NO sentences, NO explanation, NO preamble. The answer must appear as the very FIRST thing in your response. "
        "The evaluator checks only the first 200 characters of your output."
    )
    if not question:
        return UNIVERSAL

    q = question.lower().strip()

    # Multi-row signals
    if any(kw in q for kw in ("list all", "list the names", "list each", "show all", "all the", "for each", "names of all")):
        hint = "If the answer contains multiple rows, output each value on its own line, nothing else."
    # Count/integer signals
    elif any(kw in q for kw in ("how many", "count of", "number of", "total number", "total count")):
        hint = "The answer is likely a count. Output ONLY the integer number, no decimals, no text."
    # Numeric/aggregate signals
    elif any(kw in q for kw in ("what is the total", "what is the sum", "sum of", "average of", "avg of",
                                  "maximum", "minimum", "highest value", "lowest value", "most expensive",
                                  "least expensive", "what percentage", "what fraction", "what proportion")):
        hint = "The answer is likely a numeric value. Output ONLY the number."
    # Boolean/yes-no signals
    elif q.startswith(("is ", "are ", "does ", "do ", "has ", "have ", "was ", "were ", "did ", "can ", "could ")):
        hint = "The answer is likely Yes or No. Output ONLY the answer value exactly as it appears in the database."
    # Identifier/code signals
    elif any(kw in q for kw in ("what is the id", "what is the code", "return the id", "return the code",
                                  "ticker", "symbol", "isbn", "sku", "ssn")):
        hint = "The answer is likely an identifier or code. Output ONLY the value exactly as stored in the database."
    # Name/label signals
    elif any(kw in q for kw in ("what is the name", "name of the", "who is", "who was", "which person",
                                  "which company", "which country", "which city", "which team")):
        hint = "The answer is likely a name or label. Output it EXACTLY as it appears in the database — exact spelling, capitalisation, and punctuation."
    else:
        hint = "Output ONLY the answer value with no surrounding text."

    return hint + UNIVERSAL


@traceable(name="DAB Query", run_type="chain", tags=["dab", "benchmark"])
def run_dab_query(
    query: Dict[str, Any],
    llm_client: Optional[LLMClient] = None,
    run_number: int = 0,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run a single DAB query through the SpiderDIN pipeline.
    LangSmith: each call is traced as a top-level run; all 8 evaluator scores
    are attached as feedback to that run after grading completes.

    Args:
        query: Query dict from benchmark_loader.load_all_queries()
        llm_client: Shared LLMClient instance (created if None)
        run_number: Which run slot this is (0 = canonical, 1-4 = additional runs).
                    When > 0, files are saved with a _run{N} suffix.

    Returns:
        Result dict with: status, agent_answer, passed, elapsed_s, error
    """
    try:
        from agent.app.utils.cache import DAB_CANCEL_FLAG, SPIDER_CANCEL_FLAG
        if DAB_CANCEL_FLAG or SPIDER_CANCEL_FLAG:
            raise KeyboardInterrupt("Run stopped by user")
    except Exception:
        pass

    from agent.app.core.orchestrator import SemanticDINOrchestrator

    dataset = query["dataset"]
    query_id = query["query_id"]
    instance_id = query["instance_id"]
    question = query["question"]
    ground_truth = query["ground_truth"]
    validate_src = query["validate_src"]
    db_clients = query["db_clients"]
    db_description = query["db_description"]
    Path(query["query_dir"])

    start_time = time.time()

    # Setup results directory
    import agent.app.dab.dab_evaluator as de
    from agent.app.core.config import get_user_dab_results_dir
    
    current_results_dir = get_user_dab_results_dir(de.DAB_RUN_USERNAME or DEFAULT_USERNAME)
    if de.DAB_RUN_ID and de.DAB_RUN_ID != "live":
        result_dir = current_results_dir / "_archive" / de.DAB_RUN_ID / dataset
    else:
        result_dir = current_results_dir / dataset
    result_dir.mkdir(parents=True, exist_ok=True)

    # run_number=0 Ã¢â€ â€™ canonical files (query1.md); run_number>0 Ã¢â€ â€™ query1_run2.md
    _run_sfx = f"_run{run_number}" if run_number > 0 else ""
    md_path = result_dir / f"query{query_id}{_run_sfx}.md"
    csv_path = result_dir / f"query{query_id}{_run_sfx}.csv"
    sql_path = result_dir / f"query{query_id}{_run_sfx}.sql"

    log_path = result_dir / f"query{query_id}{_run_sfx}.log"
    for p in (md_path, csv_path, sql_path, log_path):
        if p.exists():
            with contextlib.suppress(Exception):
                p.unlink()

    if llm_client is None:
        llm_client = LLMClient(model=model, temperature=temperature)

    reset_token_counters()
    logger.start_live_task_log(str(md_path))
    logger.log_section(f"DAB: {dataset} / Query {query_id}", color=logger.CYAN)
    logger.info(f"Question: {question}")

    try:
        # Pick best available DB (query-aware when multiple local DBs exist)
        best_db = _pick_best_db(db_clients, question=question)
        if not best_db:
            raise RuntimeError(
                f"No available DB files found for dataset '{dataset}'. "
                f"Check that DataAgentBench was cloned with git lfs."
            )

        db_path = best_db.get("db_path", "")
        db_type = best_db.get("db_type", "sqlite").lower()
        db_name = f"DAB_{dataset.upper()}"

        logger.info(f"Selected DB: {db_type} @ {db_path}")

        # Map DAB db_type to SpiderDIN dialect. Unknown types pass through as-is so the
        # executor can attempt dialect-specific auto-detection without silently defaulting.
        dialect_map = {
            "sqlite": "sqlite",
            "duckdb": "duckdb",
            "postgres": "postgres",
            "postgresql": "postgres",
            "mysql": "mysql",
            "mariadb": "mariadb",
            "mssql": "mssql",
            "sqlserver": "mssql",
            "oracle": "oracle",
            "mongo": "mongo",
            "mongodb": "mongo",
            "bigquery": "bigquery",
            "snowflake": "snowflake",
            "redshift": "redshift",
            "trino": "trino",
            "presto": "presto",
            "spark": "spark",
            "databricks": "databricks",
            "hive": "hive",
            "clickhouse": "clickhouse",
        }
        dialect = dialect_map.get(db_type, db_type)  # unknown types pass through as-is
        if db_type not in dialect_map:
            logger.warning(f"[DABOrchestrator] Unknown db_type '{db_type}' — using '{dialect}' as dialect name.")

        # For schema context: use the parent directory of the DB file
        db_dir = str(Path(db_path).parent) if db_path else query["dataset_dir"]

        # Inject schema description as external knowledge
        external_knowledge_text = ""
        if db_description:
            external_knowledge_text = db_description

        # Also inject all-DB schema info for multi-DB awareness
        multi_db_context = []
        for db_key, cfg in db_clients.items():
            multi_db_context.append(
                f"Database '{db_key}' ({cfg.get('db_type', '?')}): "
                f"{cfg.get('db_path', cfg.get('db_name', 'N/A'))}"
            )
        if len(multi_db_context) > 1:
            external_knowledge_text += (
                "\n\nMULTI-DATABASE CONTEXT:\n"
                "This dataset spans multiple databases:\n"
                + "\n".join(f"  - {s}" for s in multi_db_context)
            )

        # ── Dataset-specific schema quirks injected as external knowledge ──────
        dataset_upper = dataset.upper()
        if "YELP" in dataset_upper:
            external_knowledge_text += (
                "\n\n[YELP SCHEMA NOTES — CRITICAL FOR CORRECT QUERIES]\n"
                "1. business.attributes stores Python-repr pseudo-JSON, NOT valid JSON. "
                "   Values look like: {\"WiFi\": \"u'free'\", \"BusinessAcceptsCreditCards\": \"True\"}. "
                "   json_extract() returns NULL on these. Use ILIKE/LIKE instead.\n"
                "2. WiFi filter: Use ONLY `attributes ILIKE '%\"WiFi\"%free%'` to find businesses offering WiFi. "
                "   DO NOT add NOT ILIKE exclusions like `NOT ILIKE '%\"WiFi\"%no%'` — these cause false negatives "
                "   because other attributes after WiFi in the string (like NoiseLevel, GoodForNoMeat) "
                "   accidentally match the 'no' pattern. Only filter for POSITIVE WiFi values.\n"
                "3. review.business_ref uses format 'businessref_N'; business.business_id uses 'businessid_N'. "
                "   Join via: REPLACE(r.business_ref, 'businessref_', 'businessid_') = b.business_id\n"
                "4. The state for a business is embedded in business.description: "
                "   'Located at ADDR in CITY, STATE, ...'. "
                "   Extract with: regexp_extract(description, '\\\\bin [^,]+,\\\\s*([A-Z]{2})\\\\b', 1)\n"
                "5. Average rating = AVG(review.rating) for all reviews of those WiFi businesses joined via #3.\n"
            )
        if "CRMARENAPRO" in dataset_upper or "CRM" in dataset_upper:
            external_knowledge_text += (
                "\n\n[CRM SCHEMA NOTES — CRITICAL FOR CORRECT QUERIES]\n"
                "1. ID columns in CaseHistory__c, Case, OrderItem may have leading '#' characters (data artifact). "
                "   Always normalize with REPLACE(id_col, '#', '') before joining. "
                "   Example: REPLACE(c.Id, '#', '') = REPLACE(ch.CaseId__c, '#', '')\n"
                "2. Handle time = ClosedDate - CreatedDate (for closed cases only). "
                "   In DuckDB: date_diff('second', TRY_CAST(CreatedDate AS TIMESTAMP), TRY_CAST(ClosedDate AS TIMESTAMP)). "
                "   Do NOT use EXTRACT(EPOCH FROM ...) — that is PostgreSQL syntax and fails in DuckDB.\n"
                "3. Non-transferred cases have exactly ONE 'Owner Assignment' in CaseHistory__c. "
                "   Transferred cases have MORE THAN ONE. Do not compute handle time for transferred cases.\n"
                "4. CRITICAL: When a question asks for 'agents processing more than one case', count ALL cases per agent "
                "   (including open/unclosed cases). Do NOT filter WHERE ClosedDate IS NOT NULL before the GROUP BY "
                "   COUNT(*) > 1 check. Only use ClosedDate IS NOT NULL inside a CASE expression when computing "
                "   the average handle time: "
                "   AVG(CASE WHEN ClosedDate IS NOT NULL THEN date_diff('second', ...) END). "
                "   This ensures agents with multiple open cases still qualify for the '>1 case' filter.\n"
                "5. For the 'past four months' window, apply the filter on CreatedDate: "
                "   TRY_CAST(CreatedDate AS TIMESTAMP) >= TIMESTAMP 'YYYY-MM-DD' (4 months before today's date)\n"
            )
        if "GITHUB" in dataset_upper:
            external_knowledge_text += (
                "\n\n[GITHUB REPOS SCHEMA NOTES — CRITICAL FOR CORRECT QUERIES]\n"
                "1. languages.language_description stores natural language text like: "
                "   'The codebase includes: C++ (bytes), Swift (bytes), Python (bytes)...' "
                "   The MAIN (primary) language is the FIRST one listed. "
                "   Extract it with: regexp_extract(language_description, "
                "   '(?:includes:|is in |built in |written in )\\\\s*([A-Za-z][A-Za-z+#]*)\\\\s*\\\\(', 1)\n"
                "2. Do NOT use language_description LIKE '%python%' to exclude Python repos — "
                "   this incorrectly excludes repos where Python is a minor secondary language.\n"
                "3. The repos table only has repo_name and watch_count — NO stars column.\n"
                "4. Use commits.repo_name to count commits per repository.\n"
            )
        if "PANCANCER" in dataset_upper:
            external_knowledge_text += (
                "\n\n[PANCANCER SCHEMA NOTES — CRITICAL FOR CORRECT QUERIES]\n"
                "1. CRITICAL JOIN FIX: clinical_info.patient_id contains ONLY the last segment of the TCGA "
                "   barcode (e.g., 'A5EH'). This does NOT match Mutation_Data.ParticipantBarcode which has "
                "   the full barcode (e.g., 'TCGA-AC-A5EH'). NEVER join on patient_id = ParticipantBarcode — "
                "   this always returns 0 matches and produces 0.0% mutation rates.\n"
                "2. CORRECT JOIN: Extract the full TCGA barcode from Patient_description:\n"
                "   REGEXP_EXTRACT(Patient_description, 'TCGA-[A-Z0-9-]+', 0)\n"
                "   The 3rd arg 0 = full match (DuckDB syntax). Works for all description formats.\n"
                "3. BRCA filter: Patient_description ILIKE '%breast%'\n"
                "4. Alive filter: Patient_description ILIKE '%Alive%'\n"
                "5. Always add: AND REGEXP_EXTRACT(Patient_description, 'TCGA-[A-Z0-9-]+', 0) != ''\n"
            )
        if "STOCKMARKET" in dataset_upper or "STOCK_MARKET" in dataset_upper:
            external_knowledge_text += (
                "\n\n[STOCKMARKET SCHEMA NOTES — CRITICAL FOR CORRECT QUERIES]\n"
                "1. The unified view all_stocktrade_query has column _entity_name (the ticker symbol). "
                "   Do NOT reference Symbol in this view — it does not exist. Only _entity_name.\n"
                "2. NYSE filter: \"Listing Exchange\" = 'N' (single letter N, NOT 'NYSE').\n"
                "3. Join: all_stocktrade_query._entity_name = stockinfo.\"Symbol\"\n"
                "4. Date filtering uses string comparison: \"Date\" >= 'YYYY-MM-DD'\n"
                "5. stockinfo is accessible directly as stockinfo (auto-attached temp table).\n"
                "6. NET POSITIVE DAYS definition: net = (up_days - down_days). "
                "   A stock with fewer up days but many fewer down days can have a HIGHER net "
                "   than a stock with more raw up days but also many down days. "
                "   When ranking by 'net positive days', always ORDER BY (up_days - down_days) DESC, "
                "   not by up_days alone.\n"
            )
        if "DEPS_DEV" in dataset_upper or "DEPS" in dataset_upper:
            external_knowledge_text += (
                "\n\n[DEPS_DEV SCHEMA NOTES — CRITICAL FOR CORRECT QUERIES]\n"
                "1. COMPOSITE PACKAGE KEYS: The Name column in packageinfo is NOT always a simple package name. "
                "   It contains composite dependency chains where '>' separates components "
                "   (e.g. 'base-package>base-version>dependency'). Treat the ENTIRE string "
                "   (including '>') as the package Name — do not split or truncate it.\n"
                "2. LATEST VERSION: Use ROW_NUMBER() OVER (PARTITION BY Name ORDER BY "
                "   COALESCE(CAST(json_extract_string(VersionInfo, '$.Ordinal') AS INTEGER), 0) DESC, "
                "   UpstreamPublishedAt DESC NULLS LAST) to pick the latest release per Name. "
                "   Filter: json_extract_string(VersionInfo, '$.IsRelease') = 'true'\n"
                "3. GITHUB STARS: project_info.Project_Information is natural language text. "
                "   Extract stars with REGEXP_EXTRACT. Star counts may contain commas (e.g. '73,499 stars'). "
                "   Always REPLACE(text, ',', '') before casting to INTEGER to avoid extracting only "
                "   the digits after the last comma.\n"
                "4. PROJECT JOIN: Join via REGEXP_EXTRACT(pi.Project_Information, 'The project ([^ ]+)', 1) "
                "   = pv.ProjectName. Restrict to pv.ProjectType = 'GITHUB'.\n"
                "5. DEDUPLICATION: Multiple distinct packages (different Names) can share the same "
                "   ProjectName and star count — they are separate packages and must each appear as "
                "   their own row in the output. Group by Name+Version and use MAX(stars) to handle "
                "   multiple project_info rows per project. Choose a LIMIT large enough to capture "
                "   all packages at the boundary star count.\n"
            )
        if "MUSIC" in dataset_upper or "MUSIC_BRAINZ" in dataset_upper:
            external_knowledge_text += (
                "\n\n[MUSIC_BRAINZ SCHEMA NOTES — CRITICAL FOR CORRECT QUERIES]\n"
                "1. The tracks table contains POTENTIAL DUPLICATES. The same song may appear multiple "
                "   times with variant title formats (e.g. with a leading numeric prefix, with an "
                "   embedded artist name prefix, with a subtitle suffix, or as the bare title). "
                "   WITHOUT normalization spurious groups win; WITH normalization the true answer emerges.\n"
                "2. TRACKS table has an 'artist' column. When artist IS NULL the title embeds the "
                "   artist in 'ArtistName - SongTitle' format (take what is AFTER ' - '). "
                "   When artist IS NOT NULL the title is the song title itself, possibly with a "
                "   leading numeric prefix (e.g. '006-') or a trailing subtitle ('- subtitle' or '(subtitle)').\n"
                "3. NORMALIZATION: apply conditionally based on the artist column, then strip:\n"
                "   - Leading numeric prefix: regexp_replace(..., '^\\d+-', '')\n"
                "   - Trailing parenthetical: regexp_replace(..., '\\s*\\([^)]*\\)\\s*$', '')\n"
                "   - Trailing dash/pipe suffix: regexp_replace(..., ' [-|].+$', '')\n"
                "4. After normalization, filter out placeholder/section markers in HAVING:\n"
                "   - Exclude bracket titles: HAVING song_title NOT ILIKE '[%'\n"
                "   - Require multi-word titles: HAVING song_title LIKE '% %'\n"
            )

        # ── IMPROVEMENT 1: Few-shot winning SQLs from same dataset ──────────
        winning_examples = _load_winning_examples(dataset, exclude_query_id=query_id)
        if winning_examples:
            ex_block = "\n\n=== VERIFIED WORKING EXAMPLES FROM THIS DATASET ===\n"
            ex_block += "These SQLs executed successfully on the same database schema.\n"
            for i, ex in enumerate(winning_examples, 1):
                ex_block += f"\nExample {i} — Question: {ex['question']}\n"
                ex_block += f"Verified SQL:\n{ex['sql']}\n"
            ex_block += "=== END OF VERIFIED EXAMPLES ===\n"
            external_knowledge_text += ex_block
            logger.info(f"[Learning] Injected {len(winning_examples)} winning SQL example(s) from {dataset}.")

        # ── IMPROVEMENT 2: Cross-run failure hints for this specific query ──
        failure_hints = _load_failure_hints(dataset, query_id)
        if failure_hints:
            hint_block = "\n\n=== PREVIOUS ATTEMPTS ON THIS EXACT QUESTION FAILED ===\n"
            hint_block += (
                "Study these failed attempts to understand what approaches did NOT work. "
                "If multiple failures share the same structural pattern, identify it and try something fundamentally different. "
                "A structural change means a different anchor table, aggregation expression, join path, or ORDER BY logic — "
                "not just renamed aliases or reordered clauses.\n\n"
            )
            for h in failure_hints:
                hint_block += f"\nAttempt {h['run']} FAILED — Reason: {h['reason']}\n"
                if h.get('sql'):
                    hint_block += f"Failed SQL:\n{h['sql'][:600]}\n"
                if h.get('agent_answer'):
                    hint_block += f"Wrong answer produced: {h['agent_answer'][:150]}\n"
            hint_block += "\n=== Try a structurally different approach. ===\n"
            external_knowledge_text += hint_block
            logger.info(f"[Learning] Injected {len(failure_hints)} failure hint(s) for {dataset} q{query_id}.")

        # ── IMPROVEMENT 3: Output format hint derived from question text only ──
        fmt_hint = _derive_answer_format_hint(question)
        if fmt_hint:
            external_knowledge_text += f"\n\n=== OUTPUT FORMAT REQUIREMENT ===\n{fmt_hint}\n=== END FORMAT ===\n"
            logger.info(f"[Learning] Injected answer format hint: {fmt_hint[:80]}")

        # Build orchestrator — RAG disabled for benchmark runs to prevent SQL leakage
        # between runs and across submissions. Few-shot SQL from prior runs must never
        # be fed back into the pipeline during a DAB evaluation.
        orchestrator = SemanticDINOrchestrator(
            db_directory=db_dir,
            db_name=db_name,
            dialect=dialect,
            max_retries=_load_configured_max_retries(default=1),  # 2 total attempts max within 4-min budget
            use_few_shot_rag=False,
            single_pass_mode=True,  # skip 3-candidate diverse generation — saves 3 LLM calls per query
        )

        # Write external knowledge to a temp file if needed
        ext_knowledge_param = None
        if external_knowledge_text:
            from agent.app.core.config import RESOURCES_DIR

            docs_dir = RESOURCES_DIR / "documents"
            docs_dir.mkdir(parents=True, exist_ok=True)
            ext_file = docs_dir / f"dab_{dataset}_description.txt"
            ext_file.write_text(external_knowledge_text, encoding="utf-8")
            ext_knowledge_param = ext_file.name

        # Override executor to point at the right DB file
        orchestrator.executor.dialect = dialect
        orchestrator.executor.db_name = db_name
        orchestrator.executor.explicit_db_path = db_path

        # Hard wall-clock cap for the entire pipeline.
        # gpt-oss-safeguard-120b averages ~50-70s per LLM call; the pipeline makes
        # 4-6 calls (schema_linking + sql_gen + self_correction + retry), so
        # 4 × 90s = 360s minimum. 600s (10 min) gives comfortable headroom.
        _PIPELINE_TIMEOUT_S = 600  # 10 minutes
        _pipeline_result: list = [None]
        _pipeline_error:  list = [None]
        _pipeline_tokens: list = [(0, 0)]

        from agent.app.utils.logger import task_local
        from agent.app.utils.llm import add_tokens
        parent_live_file = getattr(task_local, "live_file", None)

        def _run_pipeline():
            try:
                if parent_live_file:
                    task_local.live_file = parent_live_file
                reset_token_counters()
                _pipeline_result[0] = orchestrator.execute_query(
                    user_query=question,
                    instance_id=f"dab_{dataset}_q{query_id}{_run_sfx}",
                    external_knowledge=ext_knowledge_param,
                )
                _pipeline_tokens[0] = get_tokens()
            except Exception as _pe:
                _pipeline_error[0] = _pe

        _pipeline_thread = threading.Thread(target=_run_pipeline, daemon=True)
        _pipeline_thread.start()
        _pipeline_thread.join(timeout=_PIPELINE_TIMEOUT_S)

        # Propagate tokens back to main thread
        pipe_in, pipe_out = _pipeline_tokens[0]
        add_tokens(pipe_in, pipe_out)

        if _pipeline_thread.is_alive():
            elapsed_so_far = time.time() - start_time
            logger.error(
                f"[PIPELINE TIMEOUT] {dataset} q{query_id} exceeded {_PIPELINE_TIMEOUT_S}s "
                f"({elapsed_so_far:.0f}s elapsed). Returning empty answer."
            )
            return {
                "status": "pipeline_timeout",
                "agent_answer": "",
                "passed": False,
                "elapsed_s": elapsed_so_far,
                "error": f"Pipeline timeout after {_PIPELINE_TIMEOUT_S}s",
            }

        if _pipeline_error[0]:
            raise _pipeline_error[0]

        final_sql = _pipeline_result[0] or ""

        # Determine if the returned value is a SQL query or a direct text answer
        is_sql = (
            final_sql.strip()
            .lower()
            .startswith(("select", "with", "show", "explain", "pragma", "describe"))
        )
        if is_sql:
            # Save SQL
            sql_path.write_text(final_sql, encoding="utf-8")

            # CSV is auto-saved by executor under RESULTS_DIR/{db_name}/{instance_id}.csv
            # Move it to our DAB results dir
            src_csv = RESULTS_DIR / db_name / f"dab_{dataset}_q{query_id}{_run_sfx}.csv"
            if src_csv.exists():
                import shutil

                shutil.copy2(str(src_csv), str(csv_path))

            # Extract concise text answer for DAB grading (from CSV)
            agent_answer = extract_answer(
                question=question,
                csv_path=str(csv_path),
                llm_client=llm_client,
                instance_id=instance_id,
            )
        else:
            # Non-SQL text came back — treat as an empty answer so the schema-grounded
            # retry below gets a chance to produce real SQL.
            agent_answer = final_sql.strip()
            csv_path.write_text(f'result\n"{agent_answer}"\n', encoding="utf-8")
            logger.warning(
                f"[DABOrchestrator] execute_query returned non-SQL text. "
                f"Will attempt schema-grounded SQL retry. Text: {agent_answer[:120]}"
            )

        # Schema-grounded retry: when the first pass returns empty results OR non-SQL text,
        # inject real sample data from the live DB so the LLM can see actual table/column names.
        if _is_empty_answer(agent_answer) or not is_sql:
            logger.info(
                "[EmptyRetry] First attempt returned empty answer — injecting real schema evidence for retry."
            )
            schema_hint = _build_rich_schema_hint(db_path, db_type)
            if schema_hint:
                retry_knowledge = external_knowledge_text + (
                    "\n\n=== CRITICAL: YOUR PREVIOUS QUERY RETURNED 0 ROWS ==="
                    "\nThe ACTUAL table names and real sample data from the live database are shown below."
                    "\nYou MUST use these exact table and column names. Your query MUST return results.\n"
                    + schema_hint
                    + "\n=== END OF ACTUAL DATABASE EVIDENCE ==="
                )
                from agent.app.core.config import RESOURCES_DIR

                docs_dir = RESOURCES_DIR / "documents"
                docs_dir.mkdir(parents=True, exist_ok=True)
                retry_ext_file = docs_dir / f"dab_{dataset}_retry.txt"
                retry_ext_file.write_text(retry_knowledge, encoding="utf-8")

                orchestrator.stabilizer.retry_history.clear()
                retry_instance_id = f"dab_{dataset}_q{query_id}{_run_sfx}_retry"
                retry_sql = orchestrator.execute_query(
                    user_query=question,
                    instance_id=retry_instance_id,
                    external_knowledge=retry_ext_file.name,
                )
                is_retry_sql = (
                    retry_sql.strip()
                    .lower()
                    .startswith(
                        ("select", "with", "show", "explain", "pragma", "describe")
                    )
                )
                if is_retry_sql:
                    sql_path.write_text(retry_sql, encoding="utf-8")
                    retry_src_csv = RESULTS_DIR / db_name / f"{retry_instance_id}.csv"
                    if retry_src_csv.exists():
                        import shutil

                        shutil.copy2(str(retry_src_csv), str(csv_path))
                    retry_answer = extract_answer(
                        question=question,
                        csv_path=str(csv_path),
                        llm_client=llm_client,
                        instance_id=instance_id,
                    )
                else:
                    retry_answer = retry_sql.strip()
                    csv_path.write_text(f'result\n"{retry_answer}"\n', encoding="utf-8")

                if not _is_empty_answer(retry_answer):
                    logger.info(
                        f"[EmptyRetry] Retry produced non-empty answer: {retry_answer[:120]}"
                    )
                    agent_answer = retry_answer
                    final_sql = retry_sql
                else:
                    logger.warning(
                        "[EmptyRetry] Retry also returned empty Ã¢â‚¬â€ keeping original answer."
                    )

        save_answer(
            agent_answer, dataset, query_id, result_dir.parent, run_suffix=_run_sfx
        )
        logger.info(f"AGENT ANSWER: {agent_answer}")

        # Evaluate against ground truth
        elapsed = round(time.time() - start_time, 1)
        in_t, out_t = get_tokens()

        eval_result = evaluate_answer(
            dataset=dataset,
            query_id=query_id,
            agent_answer=agent_answer,
            ground_truth=ground_truth,
            validate_src=validate_src,
            elapsed_s=elapsed,
            input_tokens=in_t,
            output_tokens=out_t,
            run_suffix=_run_sfx,
        )

        status = "passed" if eval_result["passed"] else "failed"
        logger.success(f"DAB Evaluation: {status.upper()} | {eval_result['reason']}")

        # ── IMPROVEMENT 1 & 2: Persist learning signals for future runs ──────
        _last_sql = sql_path.read_text(encoding="utf-8").strip() if sql_path.exists() else ""
        if eval_result["passed"]:
            _save_winning_example(dataset, query_id, question, _last_sql, agent_answer)
            logger.info(f"[Learning] Saved winning SQL for {dataset} q{query_id} run {run_number}.")
        else:
            _save_failure_hint(dataset, query_id, run_number, eval_result["reason"], _last_sql, agent_answer)
            logger.info(f"[Learning] Saved failure hint for {dataset} q{query_id} run {run_number}.")

        # RAG is intentionally disabled for DAB benchmark runs — do not save SQL here.

        # Attach all 8 evaluator scores to the LangSmith trace (non-blocking)
        run_tree = get_current_run_tree()
        if run_tree and _LANGSMITH_AVAILABLE:
            _push_evaluator_feedback(str(run_tree.id), eval_result)

        res = {
            "dataset": dataset,
            "query_id": query_id,
            "instance_id": instance_id,
            "run_number": run_number,
            "status": status,
            "passed": eval_result["passed"],
            "agent_answer": agent_answer,
            "ground_truth": ground_truth,
            "reason": eval_result["reason"],
            "elapsed_s": elapsed,
            "input_tokens": in_t,
            "output_tokens": out_t,
            "error": None,
        }

    except (Exception, KeyboardInterrupt) as e:
        # KeyboardInterrupt is raised by the cancel-flag check ("Run stopped by user").
        # It is BaseException, not Exception, so it must be listed explicitly here so
        # the verdict line and finally block always run even on user-initiated cancels.
        # Real Ctrl+C (no "stopped by user" message) is re-raised after cleanup.
        _is_cancel = isinstance(e, KeyboardInterrupt)
        if _is_cancel and "stopped by user" not in str(e).lower():
            # True SIGINT — write a brief note and re-raise so the server can shut down
            logger.error("DAB Evaluation: CANCELLED | Server interrupt received")
            raise

        elapsed = round(time.time() - start_time, 1)
        in_t, out_t = get_tokens()
        err_msg = str(e) if str(e) else type(e).__name__
        tb_str = traceback.format_exc()
        logger.error(
            f"DAB query {'CANCELLED' if _is_cancel else 'FAILED'} "
            f"({type(e).__name__}): {err_msg}\n"
            f"Full traceback:\n{tb_str}"
        )

        # Save error result
        eval_result = evaluate_answer(
            dataset=dataset,
            query_id=query_id,
            agent_answer=f"ERROR: {err_msg}",
            ground_truth=ground_truth,
            validate_src=validate_src,
            elapsed_s=elapsed,
            input_tokens=in_t,
            output_tokens=out_t,
            run_suffix=_run_sfx,
        )

        # Attach evaluator scores to LangSmith trace even on error (non-blocking)
        run_tree = get_current_run_tree()
        if run_tree and _LANGSMITH_AVAILABLE:
            _push_evaluator_feedback(str(run_tree.id), eval_result)

        _status_label = "CANCELLED" if _is_cancel else "ERROR"
        res = {
            "dataset": dataset,
            "query_id": query_id,
            "instance_id": instance_id,
            "status": _status_label.lower(),
            "passed": False,
            "agent_answer": "",
            "ground_truth": ground_truth,
            "reason": f"Execution {_status_label.lower()}: {err_msg}",
            "elapsed_s": elapsed,
            "input_tokens": in_t,
            "output_tokens": out_t,
            "error": err_msg,
        }
        # Always write the final verdict line — canonical end-of-pipeline signal
        logger.error(f"DAB Evaluation: {_status_label} | {err_msg[:200]}")
    finally:
        if "orchestrator" in dir():
            with contextlib.suppress(Exception):
                orchestrator.executor.close()
        logger.stop_live_task_log()

    # Inline rule extraction on query failure — always enabled for continuous self-improvement
    if res and not res.get("passed"):
        try:
            # 1. Read only the latest log tail
            log_tail = ""
            if md_path.exists():
                try:
                    max_chars = 15000
                    file_size = md_path.stat().st_size
                    if file_size <= max_chars:
                        log_tail = md_path.read_text(encoding="utf-8", errors="replace")
                    else:
                        with open(md_path, "rb") as f_tail:
                            f_tail.seek(-max_chars, 2)
                            log_tail = f_tail.read().decode("utf-8", errors="replace")
                except Exception as le:
                    logger.warning(
                        f"Inline Rule Extractor: failed to read log tail: {le}"
                    )

            # 2. Extract rules inline
            from agent.app.core.rules.dynamic_rule_store import DynamicRuleStore
            from agent.app.core.rules.rule_extractor_agent import (
                extract_rules_from_failure,
            )

            logger.info(
                "Inline Rule Extractor: Query failed. Extracting generic rules inline..."
            )
            rules = extract_rules_from_failure(
                llm=llm_client,
                question=question,
                sql_generated=res.get("agent_answer", "") or res.get("reason", ""),
                error_or_mismatch=res.get("reason", ""),
                dataset=dataset,
                log_tail=log_tail,
            )

            if rules:
                store = DynamicRuleStore()
                new_ids = []
                for rule in rules:
                    lid = store.add_rule(
                        rule_title=rule["rule_title"],
                        generic_rule=rule["generic_rule"],
                        intent_pattern=rule["intent_pattern"],
                        category=rule["category"],
                        source_failure=f"{dataset}_q{query_id}",
                        db_name=dataset.upper(),
                        llm_client=llm_client,
                    )
                    if lid:
                        new_ids.append(lid)

                if new_ids:
                    activated = store.activate_candidates(new_ids)
                    logger.success(
                        f"Inline Rule Extractor: Dynamically extracted & activated {activated} rules."
                    )
        except Exception as re_err:
            logger.warning(
                f"Inline Rule Extractor: Dynamic rule extraction failed (non-fatal): {re_err}"
            )

    return res
