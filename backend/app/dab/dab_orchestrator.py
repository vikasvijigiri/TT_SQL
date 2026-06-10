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

import os
import re
import json
import time
import traceback
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import yaml

from backend.app.utils.logger import logger
from backend.app.utils.llm import LLMClient, reset_token_counters, get_tokens
from backend.app.core.config import RESULTS_DIR, DAB_REPO
from backend.app.dab.answer_extractor import extract_answer, save_answer, load_answer
from backend.app.dab.dab_evaluator import evaluate_answer, load_eval_result

# LangSmith tracing — imported lazily so missing keys never crash the pipeline
try:
    from langsmith import traceable
    from langsmith.run_helpers import get_current_run_tree
    _LANGSMITH_AVAILABLE = True
except ImportError:
    _LANGSMITH_AVAILABLE = False
    traceable = lambda **kw: (lambda fn: fn)  # no-op decorator
    get_current_run_tree = lambda: None


def _push_evaluator_feedback(run_id: str, eval_json: dict) -> None:
    """
    Post all 8 evaluator scores to a LangSmith run ID in a background thread.
    Thread is non-daemon so it always completes before process exit.
    The pipeline won't wait for it — the thread runs concurrently with the
    next query, so there is zero added latency to the benchmark.
    """
    def _worker():
        try:
            from backend.app.core.langsmith_evaluators import attach_feedback_to_run
            attach_feedback_to_run(run_id, eval_json)
        except Exception:
            pass  # never crash the pipeline over telemetry
    t = threading.Thread(target=_worker, daemon=False)
    t.start()


DAB_RESULTS_DIR = RESULTS_DIR / "dab"
DAB_REPO_PATH = str(DAB_REPO)  # backward-compat alias; prefer DAB_REPO from config


def _load_configured_max_retries(default: int = 2) -> int:
    """Load the orchestrator retry budget from project config when available."""
    params_path = Path(__file__).resolve().parent.parent / "config" / "system_params.yaml"
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
    spaced = re.sub(r'([A-Z]+)', r' \1', text)
    tokens = re.findall(r'[a-zA-Z]{3,}', spaced.lower())
    return set(tokens)


def _get_table_names_quickly(db_path: str, db_type: str) -> List[str]:
    """Lightweight table-name introspection — no sample data, no schema."""
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
            conn = duckdb.connect(db_path, read_only=True)
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
            conn = duckdb.connect(db_path, read_only=True)
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
    {"INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "REAL", "FLOAT", "DOUBLE",
     "DECIMAL", "NUMERIC", "NUMBER", "DOUBLE PRECISION", "HUGEINT", "UBIGINT"}
)


def _count_numeric_columns(db_path: str, db_type: str) -> int:
    """Count columns with numeric/quantitative data types — used as analytic richness signal."""
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

    # DB name substring bonus — catches compound lowercase names (e.g. "indextrade")
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

        # Column name score — highest-signal indicator of schema content
        for col in _get_column_names_quickly(db_path, db_type):
            for tok in _tokenize(col):
                if tok in q_tokens:
                    score += 1.0

    return score


def _pick_best_db(db_clients: Dict[str, Any], question: str = "") -> Optional[Dict[str, Any]]:
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
                _count_numeric_columns(x[0].get("db_path", ""), x[0].get("db_type", "").lower()),
                len(_get_column_names_quickly(x[0].get("db_path", ""), x[0].get("db_type", "").lower())),
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
    for name, cfg in db_clients.items():
        db_path = cfg.get("db_path", "")
        if db_path and Path(db_path).exists():
            available.append(cfg)
    return available


def _make_db_directory_for_schema(db_cfg: Dict[str, Any], dataset: str) -> Optional[str]:
    """
    Return the parent directory of the selected DB file so SemanticContextEngine
    can walk it and introspect all sibling DB files in the same dataset directory.
    """
    db_path = db_cfg.get("db_path", "")
    if not db_path or not Path(db_path).exists():
        return None
    return str(Path(db_path).parent)


@traceable(name="DAB Query", run_type="chain", tags=["dab", "benchmark"])
def run_dab_query(
    query: Dict[str, Any],
    llm_client: Optional[LLMClient] = None,
    run_number: int = 0,
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
    from backend.app.core.orchestrator import SemanticDINOrchestrator

    dataset = query["dataset"]
    query_id = query["query_id"]
    instance_id = query["instance_id"]
    question = query["question"]
    ground_truth = query["ground_truth"]
    validate_src = query["validate_src"]
    db_clients = query["db_clients"]
    db_description = query["db_description"]
    query_dir = Path(query["query_dir"])

    start_time = time.time()

    # Setup results directory
    result_dir = DAB_RESULTS_DIR / dataset
    result_dir.mkdir(parents=True, exist_ok=True)

    # run_number=0 → canonical files (query1.md); run_number>0 → query1_run2.md
    _run_sfx = f"_run{run_number}" if run_number > 0 else ""
    md_path = result_dir / f"query{query_id}{_run_sfx}.md"
    csv_path = result_dir / f"query{query_id}{_run_sfx}.csv"
    sql_path = result_dir / f"query{query_id}{_run_sfx}.sql"

    for p in (md_path, csv_path, sql_path):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    if llm_client is None:
        llm_client = LLMClient()

    reset_token_counters()
    logger.start_live_task_log(str(md_path))
    logger.log_section(f"DAB: {dataset} / Query {query_id}", color=logger.CYAN)
    logger.info(f"Question: {question}")

    try:
        # Pick best available DB (query-aware when multiple local DBs exist)
        best_db = _pick_best_db(db_clients, question=question)
        if not best_db:
            raise RuntimeError(f"No available DB files found for dataset '{dataset}'. "
                               f"Check that DataAgentBench was cloned with git lfs.")

        db_path = best_db.get("db_path", "")
        db_type = best_db.get("db_type", "sqlite").lower()
        db_name = f"DAB_{dataset.upper()}"

        logger.info(f"Selected DB: {db_type} @ {db_path}")

        # Map DAB db_type to SpiderDIN dialect
        dialect_map = {
            "sqlite": "sqlite",
            "duckdb": "duckdb",
            "postgres": "postgres",
            "postgresql": "postgres",
            "mongo": "mongo",
            "mongodb": "mongo",
        }
        dialect = dialect_map.get(db_type, "sqlite")

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

        # Build orchestrator
        orchestrator = SemanticDINOrchestrator(
            db_directory=db_dir,
            db_name=db_name,
            dialect=dialect,
            max_retries=_load_configured_max_retries(default=2),
        )

        # Write external knowledge to a temp file if needed
        ext_knowledge_param = None
        if external_knowledge_text:
            from backend.app.core.config import RESOURCES_DIR
            docs_dir = RESOURCES_DIR / "documents"
            docs_dir.mkdir(parents=True, exist_ok=True)
            ext_file = docs_dir / f"dab_{dataset}_description.txt"
            ext_file.write_text(external_knowledge_text, encoding="utf-8")
            ext_knowledge_param = ext_file.name

        # Override executor to point at the right DB file
        orchestrator.executor.dialect = dialect
        orchestrator.executor.db_name = db_name
        orchestrator.executor.explicit_db_path = db_path

        # Run the query through the pipeline
        final_sql = orchestrator.execute_query(
            user_query=question,
            instance_id=f"dab_{dataset}_q{query_id}",
            external_knowledge=ext_knowledge_param,
        )

        # Determine if the returned value is a SQL query or a direct text answer
        is_sql = final_sql.strip().lower().startswith(("select", "with", "show", "explain", "pragma", "describe"))
        if is_sql:
            # Save SQL
            sql_path.write_text(final_sql, encoding="utf-8")

            # CSV is auto-saved by executor under RESULTS_DIR/{db_name}/{instance_id}.csv
            # Move it to our DAB results dir
            src_csv = RESULTS_DIR / db_name / f"dab_{dataset}_q{query_id}.csv"
            if src_csv.exists():
                import shutil
                shutil.copy2(str(src_csv), str(csv_path))

            # Extract concise text answer for DAB grading (from CSV)
            agent_answer = extract_answer(
                question=question,
                csv_path=str(csv_path),
                ground_truth=ground_truth,
                llm_client=llm_client,
                instance_id=instance_id,
            )
        else:
            # Direct text answer from diagnostic layer — use it verbatim, no CSV needed.
            # Writing through extract_answer risks reading a stale CSV from a prior run.
            agent_answer = final_sql.strip()
            csv_path.write_text(f'result\n"{agent_answer}"\n', encoding="utf-8")
        save_answer(agent_answer, dataset, query_id, DAB_RESULTS_DIR, run_suffix=_run_sfx)
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

        # Attach all 8 evaluator scores to the LangSmith trace (non-blocking)
        run_tree = get_current_run_tree()
        if run_tree and _LANGSMITH_AVAILABLE:
            _push_evaluator_feedback(str(run_tree.id), eval_result)

        return {
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

    except Exception as e:
        elapsed = round(time.time() - start_time, 1)
        in_t, out_t = get_tokens()
        err_msg = str(e)
        logger.error(f"DAB query failed: {err_msg}")
        traceback.print_exc()

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

        return {
            "dataset": dataset,
            "query_id": query_id,
            "instance_id": instance_id,
            "status": "error",
            "passed": False,
            "agent_answer": "",
            "ground_truth": ground_truth,
            "reason": f"Execution error: {err_msg}",
            "elapsed_s": elapsed,
            "input_tokens": in_t,
            "output_tokens": out_t,
            "error": err_msg,
        }
    finally:
        if "orchestrator" in dir():
            try:
                orchestrator.executor.close()
            except Exception:
                pass
        logger.stop_live_task_log()
