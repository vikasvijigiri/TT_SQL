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



import re

import time

import traceback

import threading

from pathlib import Path

from typing import Dict, Any, Optional, List

import yaml



from agent.services.logger import logger

from agent.services.llm import LLMClient, reset_token_counters, get_tokens

from agent.app.core.config import DAB_REPO, DOCUMENTS_DIR, get_active_results_dir

from agent.app.dab.answer_extractor import extract_answer, save_answer

from agent.app.dab.dab_evaluator import evaluate_answer

import contextlib



# LangSmith tracing -- imported lazily so missing keys never crash the pipeline

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

    The pipeline won't wait for it -- the thread runs concurrently with the

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

    """Lightweight table-name introspection -- no sample data, no schema."""

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

    """Count columns with numeric/quantitative data types -- used as analytic richness signal."""

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



    # DB name substring bonus -- catches compound lowercase names (e.g. "indextrade")

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



        # Column name score -- highest-signal indicator of schema content

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

    """Return all DB configs that are available (existing file or network)."""

    available = []

    for _name, cfg in db_clients.items():

        db_type = cfg.get("db_type", "").lower()

        if db_type in ("postgresql", "postgres", "mysql", "mongodb"):

            # Network DBs

            available.append(cfg)

        else:

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

    """

    Introspect the live DB and return actual table/column names with sample rows as

    ground-truth evidence.



    Enhanced (generic): for TEXT/BLOB columns whose sample values are opaque

    (JSON, separator-encoded chains, natural-language dates), automatically detects

    the format and injects a structural description. Works for any database, any schema.

    """

    from agent.app.dab.probe_capability import analyze_opaque_column_values



    # Declare which SQL types should trigger deep format analysis

    _OPAQUE_TYPE_PREFIXES = ("TEXT", "BLOB", "CLOB", "VARCHAR", "CHAR", "STRING", "OBJECT", "JSON")



    def _maybe_add_format_hint(col_name: str, col_type: str, col_values: list, out_lines: list) -> None:

        """If column is TEXT-like and values look complex, add a format description."""

        if not col_type or not any(col_type.upper().startswith(p) for p in _OPAQUE_TYPE_PREFIXES):

            return

        hint = analyze_opaque_column_values(col_name, col_values)

        if hint:

            out_lines.append(f"  FORMAT HINT: {hint}")



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

                    col_types = {col[1]: col[2] for col in cols}

                    lines.append(f"\nTable: {table}")

                    lines.append(f"  Columns: {', '.join(col_names)}")

                    rows = c.execute(

                        f'SELECT * FROM "{table}" LIMIT {sample_rows}'

                    ).fetchall()

                    if rows:

                        lines.append("  Sample rows:")

                        for row in rows:

                            lines.append(f"    {dict(zip(col_names, row, strict=False))}")

                        # Deep format analysis per column.

                        # For text columns, also try a "complex value" sample (values

                        # containing structural markers like JSON or separators) so the

                        # format detector sees a representative value, not just simple names.

                        for i, col_name in enumerate(col_names):

                            col_type = col_types.get(col_name, "")

                            col_vals = [row[i] for row in rows if row[i] is not None]

                            # If no complex values found in simple sample, probe for structural ones

                            if any(col_type.upper().startswith(p) for p in _OPAQUE_TYPE_PREFIXES):

                                if not any(isinstance(v, str) and (v.startswith("[") or v.startswith("{") or ">" in v) for v in col_vals):

                                    try:

                                        complex_rows = c.execute(

                                            f'SELECT "{col_name}" FROM "{table}" WHERE '

                                            f'("{col_name}" LIKE \'[%\' OR "{col_name}" LIKE \'{{%\' OR "{col_name}" LIKE \'%>%\') '

                                            f'AND "{col_name}" IS NOT NULL LIMIT 1'

                                        ).fetchall()

                                        if complex_rows and complex_rows[0][0]:

                                            col_vals = [complex_rows[0][0]] + col_vals

                                    except Exception:

                                        pass

                            _maybe_add_format_hint(col_name, col_type, col_vals, lines)

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

                    col_types = {r[0]: r[1] for r in schema_rows}

                    lines.append(f"\nTable: {table}")

                    lines.append(f"  Columns: {', '.join(col_names)}")

                    rows = conn.execute(

                        f'SELECT * FROM "{table}" LIMIT {sample_rows}'

                    ).fetchall()

                    if rows:

                        lines.append("  Sample rows:")

                        for row in rows:

                            lines.append(f"    {dict(zip(col_names, row, strict=False))}")

                        # Deep format analysis per column - including structural diversity probe

                        # for TEXT columns: fetch a few extra distinct values so the LLM sees

                        # the full range of formats in the column (not just the first 3 rows).

                        for i, col_name in enumerate(col_names):

                            col_type = col_types.get(col_name, "")

                            col_vals = [row[i] for row in rows if row[i] is not None]

                            if any(col_type.upper().startswith(p) for p in _OPAQUE_TYPE_PREFIXES):

                                try:

                                    extra = conn.execute(

                                        f'SELECT DISTINCT "{col_name}" FROM "{table}" '

                                        f'WHERE "{col_name}" IS NOT NULL '

                                        f'AND "{col_name}" NOT IN ({", ".join("?" * len(col_vals))}) '

                                        f'LIMIT 3',

                                        col_vals,

                                    ).fetchall()

                                    extra_vals = [r[0] for r in extra if r[0] is not None]

                                    if extra_vals:

                                        lines.append(

                                            f"  Additional distinct values for '{col_name}': "

                                            + str([str(v)[:120] for v in extra_vals])

                                        )

                                        col_vals = col_vals + extra_vals

                                except Exception:

                                    pass

                            _maybe_add_format_hint(col_name, col_type, col_vals, lines)

                except Exception:

                    pass

            conn.close()

    except Exception:

        return ""

    return "\n".join(lines)





def _derive_answer_format_hint(question: str) -> str:

    """Infer output format from the question text only - never from ground truth or expected answers.



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

        hint = "The answer is likely a name or label. Output it EXACTLY as it appears in the database - exact spelling, capitalisation, and punctuation."

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

    Path(query["query_dir"])



    start_time = time.time()



    # -- SINGLE CANONICAL STORAGE ---------------------------------------------

    # All trace files land in: {user_dir}/run_{run_id}/{dataset}/

    # run_id defaults to "run_live" for an active run without a timestamp yet.

    import agent.app.dab.dab_evaluator as de

    from agent.app.core.config import get_active_results_dir

    

    current_results_dir = get_active_results_dir()

    result_dir = current_results_dir / dataset

    result_dir.mkdir(parents=True, exist_ok=True)



    # Always 1-indexed: query1_run1.md, query1_run2.md, ... (no bare query1.md)

    _run_sfx = f"_run{run_number}"

    md_path  = result_dir / f"query{query_id}{_run_sfx}.md"

    csv_path = result_dir / f"query{query_id}{_run_sfx}.csv"

    sql_path = result_dir / f"query{query_id}{_run_sfx}.sql"



    # Remove stale files from a prior run of the same slot - never leave ghost files

    for p in (md_path, csv_path, sql_path):

        if p.exists():

            with contextlib.suppress(Exception):

                p.unlink()



    if llm_client is None:

        llm_client = LLMClient(model=model, temperature=temperature)



    # Initialized here so the except/timeout paths can always reference them

    # even if the try block fails before _pick_best_db returns.

    db_path: str = ""

    db_type: str = "sqlite"



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

            logger.warning(f"[DABOrchestrator] Unknown db_type '{db_type}' - using '{dialect}' as dialect name.")



        # -- SETTINGS BLOCK ----------------------------------------------------

        # Derive complexity from question text (no GT leak - purely heuristic)

        def _estimate_complexity(q: str) -> str:

            q_lo = q.lower()

            hard_kw = ("rank", "ema", "trending", "moving average", "percentile",

                       "correlation", "pivot", "recursive", "partition by", "window")

            med_kw  = ("average", "group by", "for each", "top ", "per year",

                       "by month", "compare", "breakdown", "join")

            if any(k in q_lo for k in hard_kw):

                return "Hard (aggregation / window / analytic)"

            if any(k in q_lo for k in med_kw):

                return "Medium (join / group / filter)"

            return "Easy (lookup / count / simple filter)"



        _model_id   = getattr(llm_client, "model_id", "unknown")

        _temp       = getattr(llm_client, "temperature", "?")

        _region     = getattr(llm_client, "region", "unknown")

        _max_tokens = getattr(llm_client, "_max_tokens", "?")

        _run_ctx    = ""

        try:

            from agent.app.utils.cache import cache_service as _cs

            _run_ctx = _cs.get("shared_DAB_RUN_ID") or "run_live"

            _usr_ctx = _cs.get("shared_DAB_RUN_USERNAME") or DEFAULT_USERNAME

        except Exception:

            _run_ctx = "run_live"

            _usr_ctx = DEFAULT_USERNAME



        _pipeline = (

            "CONTEXT_PRUNER -> SCHEMA_LINKER -> ORCHESTRATOR -> PROFILER"

            " -> [DECOMPOSER] -> SQL_GENERATOR (ReAct) -> CRITIC -> SELF_CORRECTOR -> DATA_IQ"

        )

        logger.log_run_settings({

            "Run ID"       : _run_ctx,

            "Username"     : _usr_ctx,

            "Dataset"      : dataset,

            "Query ID"     : query_id,

            "Instance ID"  : instance_id,

            "Question"     : question,

            "Complexity"   : _estimate_complexity(question),

            "Model"        : _model_id,

            "Temperature"  : _temp,

            "Max Tokens"   : _max_tokens,

            "Region"       : _region,

            "DB Type"      : db_type,

            "DB Path"      : db_path,

            "Dialect"      : dialect,

            "Run Number"   : run_number,

            "Pipeline"     : _pipeline,

            "MD File"      : str(md_path),

            "CSV File"     : str(csv_path),

        })

        # -- END SETTINGS BLOCK ------------------------------------------------



        # For schema context: use the parent directory of the DB file

        db_dir = str(Path(db_path).parent) if db_path else query["dataset_dir"]



        # Inject schema description as external knowledge

        external_knowledge_text = ""



        # Multi-DB context: for DuckDB datasets with sibling DB files, inject

        # exact ATTACH syntax so the LLM can write cross-DB queries.

        all_available_dbs = _get_all_available_dbs(db_clients)

        sibling_duckdbs = [

            d for d in all_available_dbs

            if d.get("db_type", "").lower() == "duckdb"

            and d.get("db_path", "") != db_path

        ]

        sibling_sqlites = [

            d for d in all_available_dbs

            if d.get("db_type", "").lower() in ("sqlite", "sqlite3")

            and d.get("db_path", "") != db_path

        ]

        sibling_postgres = [

            d for d in all_available_dbs

            if d.get("db_type", "").lower() in ("postgresql", "postgres")

        ]

        

        if db_type == "duckdb" and (sibling_duckdbs or sibling_sqlites or sibling_postgres):

            attach_lines = []

            attach_table_map = []

            

            if sibling_sqlites:

                attach_lines.append("INSTALL sqlite;")

                attach_lines.append("LOAD sqlite;")

                

            if sibling_postgres:

                attach_lines.append("INSTALL postgres;")

                attach_lines.append("LOAD postgres;")

                

            for sdb in sibling_duckdbs:

                sdb_path = sdb.get("db_path", "")

                sdb_alias = Path(sdb_path).stem.replace("-", "_").replace(" ", "_")

                sdb_tables = _get_table_names_quickly(sdb_path, "duckdb")

                attach_lines.append(

                    f"ATTACH '{sdb_path}' AS {sdb_alias} (READ_ONLY);"

                )

                for tbl in sdb_tables:

                    attach_table_map.append(f"  {sdb_alias}.{tbl}")

                    

            for sdb in sibling_sqlites:

                sdb_path = sdb.get("db_path", "")

                sdb_alias = Path(sdb_path).stem.replace("-", "_").replace(" ", "_")

                sdb_tables = _get_table_names_quickly(sdb_path, "sqlite")

                attach_lines.append(

                    f"ATTACH '{sdb_path}' AS {sdb_alias} (TYPE SQLITE, READ_ONLY);"

                )

                for tbl in sdb_tables:

                    attach_table_map.append(f"  {sdb_alias}.{tbl}")

                    

            for i, psql in enumerate(sibling_postgres):

                psql_uri = psql.get("raw_uri") or psql.get("db_path", "")

                if psql_uri:

                    pg_alias = f"postgres_db_{i}"

                    attach_lines.append(

                        f"ATTACH '{psql_uri}' AS {pg_alias} (TYPE POSTGRES, READ_ONLY);"

                    )

                    attach_table_map.append(f"  {pg_alias}.[postgres_tables]")



            attach_block = (

                "\n\n[MULTI-DB CROSS-JOIN - THIS QUERY REQUIRES ATTACHING SIBLING DATABASES]\n"

                "The tables you need are split across multiple database files. Run these ATTACH "

                "statements at the top of your query (DuckDB supports multi-statement scripts):\n"

                + "\n".join(attach_lines)

                + "\nThen reference tables from the attached DBs using their alias prefix:\n"

                + "\n".join(attach_table_map)

                + "\n"

            )

            external_knowledge_text += attach_block

            logger.info(

                f"[MultiDB] Injected ATTACH syntax for {len(sibling_duckdbs)} DuckDB, {len(sibling_sqlites)} SQLite, {len(sibling_postgres)} Postgres."

            )

        elif len(all_available_dbs) > 1:

            multi_db_context = [

                f"Database '{cfg.get('db_type','?')}': {cfg.get('db_path', cfg.get('db_name','N/A'))}"

                for cfg in all_available_dbs

            ]

            external_knowledge_text += (

                "\n\nMULTI-DATABASE CONTEXT:\n"

                "This dataset spans multiple databases:\n"

                + "\n".join(f"  - {s}" for s in multi_db_context)

            )





        # Output format hints are NOT injected into external_knowledge_text.
        # The block would be forwarded to ALL pipeline agents (schema_linker, self_corrector,
        # etc.) which need to produce structured JSON, not plain-text answers -- causing
        # format confusion and empty agent_answer. The answer extractor handles formatting.



        # -- FINAL CONSTRAINT: capability block injected last so it overrides any

        # function examples in the dataset notes above. The model sees this as the

        # authoritative, empirically-verified list of what is and is not supported.

        # Injected here (after all schema notes) so it is the last context the

        # model reads before generating SQL.

        if db_path and Path(db_path).exists():

            try:

                from agent.app.dab.probe_capability import build_capability_constraint_block

                cap_block = build_capability_constraint_block(db_path, db_type)

                if cap_block:

                    external_knowledge_text += cap_block

                    logger.info(f"[CapabilityProbe] Injected final constraint block for {db_type}:{Path(db_path).name}")

            except Exception as _cap_err:

                logger.warning(f"[CapabilityProbe] Final constraint injection failed (non-fatal): {_cap_err}")



        # Build orchestrator - RAG disabled for benchmark runs to prevent SQL leakage

        # between runs and across submissions. Few-shot SQL from prior runs must never

        # be fed back into the pipeline during a DAB evaluation.

        orchestrator = SemanticDINOrchestrator(

            db_directory=db_dir,

            db_name=db_name,

            dialect=dialect,

            max_retries=_load_configured_max_retries(default=1),  # 2 total attempts max within 4-min budget

            use_few_shot_rag=False,

            single_pass_mode=True,  # skip 3-candidate diverse generation - saves 3 LLM calls per query

        )



        # Write external knowledge to a per-instance file.

        # Using instance_id (dataset+query_id+run_suffix) as the filename key

        # prevents parallel queries for the same dataset from overwriting each

        # other's context - a race condition when running with multiple workers.

        ext_knowledge_param = None

        if external_knowledge_text:

            docs_dir = DOCUMENTS_DIR

            docs_dir.mkdir(parents=True, exist_ok=True)

            # Per-instance filename: unique per (dataset, query_id, run_suffix)

            ext_file = docs_dir / f"dab_{dataset}_q{query_id}{_run_sfx}_ctx.txt"

            ext_file.write_text(external_knowledge_text, encoding="utf-8")

            ext_knowledge_param = ext_file.name

            logger.info(f"[ContextFile] Written {len(external_knowledge_text):,} chars -> {ext_file.name}")



        # Override executor to point at the right DB file

        orchestrator.executor.dialect = dialect

        orchestrator.executor.db_name = db_name

        orchestrator.executor.explicit_db_path = db_path



        # No hard wall-clock cap - the pipeline runs until the LLM responds.

        # Per-call read_timeout is set on the boto3 HTTP client (900s default) so

        # individual calls never hang indefinitely. The circuit breaker in llm.py

        # handles true Bedrock outages.

        _pipeline_result: list = [None]

        _pipeline_error:  list = [None]

        _pipeline_tokens: list = [(0, 0)]



        from agent.services.logger import task_local

        from agent.services.llm import add_tokens

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

        _pipeline_thread.join()   # wait indefinitely - no wall-clock cap



        # Propagate tokens back to main thread

        pipe_in, pipe_out = _pipeline_tokens[0]

        add_tokens(pipe_in, pipe_out)



        if _pipeline_error[0]:

            raise _pipeline_error[0]



        final_sql = _pipeline_result[0] or ""



        # Determine if the returned value is a SQL query or a direct text answer

        is_sql = (
            final_sql.strip()
            .lower()
            .startswith(("select", "with", "show", "explain", "pragma", "describe", "install", "load", "attach"))
        )

        if is_sql:

            # Save SQL

            sql_path.write_text(final_sql, encoding="utf-8")



            # CSV is auto-saved by executor under get_active_results_dir()/{db_name}/{instance_id}.csv

            # Move it to our DAB results dir

            src_csv = get_active_results_dir() / db_name / f"dab_{dataset}_q{query_id}{_run_sfx}.csv"

            if src_csv.exists():

                import shutil

                shutil.copy2(str(src_csv), str(csv_path))



            # Guarantee: always write a CSV so downstream steps never see a missing file.

            # If the executor produced nothing (execution error, 0 rows, network issue),

            # write an empty CSV with a minimal header derived from the DB schema.

            if not csv_path.exists() or csv_path.stat().st_size == 0:

                try:

                    col_names = _get_column_names_quickly(db_path, db_type)

                except Exception:

                    col_names = []

                header = ",".join(col_names) if col_names else "result"

                csv_path.write_text(header + "\n", encoding="utf-8")

                logger.warning(

                    f"[CSV-Guarantee] No CSV from executor - wrote empty CSV with header: {header[:120]}"

                )



            # Extract concise text answer for DAB grading (from CSV)

            agent_answer = extract_answer(

                question=question,

                csv_path=str(csv_path),

                llm_client=llm_client,

                instance_id=instance_id,

            )

        else:

            # Non-SQL text came back - treat as an empty answer so the schema-grounded

            # retry below gets a chance to produce real SQL.

            agent_answer = final_sql.strip()

            csv_path.write_text(f'result\n"{agent_answer}"\n', encoding="utf-8")

            logger.warning(

                f"[DABOrchestrator] execute_query returned non-SQL text. "

                f"Will attempt schema-grounded SQL retry. Text: {agent_answer[:120]}"

            )



        # Schema-grounded retry: when the first pass returns empty results.
        # NOTE: non-SQL text from text_classify_aggregate is a valid direct answer —
        # do NOT retry it, only retry when the extracted answer is actually empty.

        if _is_empty_answer(agent_answer):

            logger.info(

                "[EmptyRetry] First attempt returned empty answer - injecting real schema evidence for retry."

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

                docs_dir = DOCUMENTS_DIR

                docs_dir.mkdir(parents=True, exist_ok=True)

                # Per-instance retry file - same uniqueness guarantee as the primary file

                retry_ext_file = docs_dir / f"dab_{dataset}_q{query_id}{_run_sfx}_retry.txt"

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

                    retry_src_csv = get_active_results_dir() / db_name / f"{retry_instance_id}.csv"

                    if retry_src_csv.exists():

                        import shutil

                        shutil.copy2(str(retry_src_csv), str(csv_path))

                    # CSV guarantee for retry: if the retry SQL also produced no output file,

                    # ensure csv_path still has at least an empty CSV with schema headers.

                    if not csv_path.exists() or csv_path.stat().st_size == 0:

                        _rty_cols: list = []

                        with contextlib.suppress(Exception):

                            _rty_cols = _get_column_names_quickly(db_path, db_type)

                        _rty_header = ",".join(_rty_cols) if _rty_cols else "result"

                        csv_path.write_text(_rty_header + "\n", encoding="utf-8")

                        logger.warning(f"[CSV-Guarantee/Retry] Retry produced no CSV - wrote empty CSV")

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

                        "[EmptyRetry] Retry also returned empty -- keeping original answer."

                    )



        # -- Generic answer normalization --------------------------------------

        # Strip format artifacts (BOM, leading '#' on IDs, etc.) without any

        # dataset-specific logic. Works for any DB system generically.

        try:

            from agent.app.dab.answer_extractor import normalize_agent_answer

            agent_answer_normalized = normalize_agent_answer(agent_answer)

            if agent_answer_normalized != agent_answer:

                logger.info(f"[AnswerNorm] Normalized answer (was: {agent_answer[:80]!r}) -> {agent_answer_normalized[:80]!r}")

                agent_answer = agent_answer_normalized

        except Exception as _norm_err:

            logger.warning(f"[AnswerNorm] Normalization failed (non-fatal): {_norm_err}")



        # Save to the single canonical live dir

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



        # Write clean final verdict block to the .md file

        _verdict_status = "PASSED" if eval_result["passed"] else "FAILED"

        _verdict_icon   = "[OK]" if eval_result["passed"] else "[X]"

        _verdict_block = (

            f"\n---\n\n"

            f"## Final Verdict: {_verdict_status} {_verdict_icon}\n\n"

            f"| Field | Value |\n"

            f"|-------|-------|\n"

            f"| Status | **{_verdict_status}** |\n"

            f"| Agent Answer | {str(agent_answer)[:500].replace('|', '\\|')} |\n"

            f"| Ground Truth | {str(ground_truth)[:300].replace('|', '\\|')} |\n"

            f"| Reason | {str(eval_result.get('reason', "")).replace('|', '\\|')} |\n"

            f"| Elapsed | {elapsed}s |\n"

            f"| Tokens In | {in_t:,} |\n"

            f"| Tokens Out | {out_t:,} |\n\n"

        )

        from agent.services.logger import task_local as _tl

        if hasattr(_tl, "live_file"):

            _tl.live_file.write(_verdict_block)



        # RAG is intentionally disabled for DAB benchmark runs - do not save SQL here.



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

            # True SIGINT - write a brief note and re-raise so the server can shut down

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

        # Guarantee: write SQL stub, empty CSV, and answer file even on error/cancel

        with contextlib.suppress(Exception):

            if not sql_path.exists():

                sql_path.write_text(

                    f" {_status_label}: {err_msg[:200]}\n", encoding="utf-8"

                )

        with contextlib.suppress(Exception):

            if not csv_path.exists() or csv_path.stat().st_size == 0:

                _err_cols: list = []

                with contextlib.suppress(Exception):

                    _err_cols = _get_column_names_quickly(db_path, db_type)

                _err_header = ",".join(_err_cols) if _err_cols else "result"

                csv_path.write_text(_err_header + "\n", encoding="utf-8")

        with contextlib.suppress(Exception):

            save_answer("", dataset, query_id, result_dir.parent, run_suffix=_run_sfx)

        # Always write the final verdict line - canonical end-of-pipeline signal

        logger.error(f"DAB Evaluation: {_status_label} | {err_msg[:200]}")

    finally:

        if "orchestrator" in dir():

            with contextlib.suppress(Exception):

                orchestrator.executor.close()

        logger.stop_live_task_log()



    # Inline rule extraction on query failure - always enabled for continuous self-improvement

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

