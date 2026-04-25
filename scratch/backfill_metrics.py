"""
backfill_metrics.py
===================
Retroactively build results/pipeline_metrics.csv from existing result files.

Sources used per instance:
  - input_data/*.jsonl      → question, db, external_knowledge, dialect
  - results/{db}/{id}.sql   → final SQL (structural analysis)
  - results/{db}/{id}.csv   → result_row_count, result_col_count, has_data
  - results/{db}/{id}.md    → latencyMs per call, tables selected, timestamps,
                              complexity, iteration count, any errors
  - resources/metadata/     → full schema for db_total_tables, fk_density

Run from project root:
    python scratch/backfill_metrics.py

Optional flags:
    --db IPL           (only backfill one database folder)
    --overwrite        (re-process instances that already exist in the CSV)
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── project root & sys.path ───────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from core.metrics_tracker import (
    COLUMNS,
    _metrics_path,
    _classify_question,
    _fk_density,
    _join_count,
    _kw,
    _model_cost,
    _sql_complexity,
    _total_columns,
    _ensure_header,
    _load_existing,
)
from core.paths import RESULTS_BASE_DIR, METADATA_DIR, DATA_DIR


# ────────────────────────────────────────────────────────────────────────────────
# Log parsing helpers
# ────────────────────────────────────────────────────────────────────────────────

def _parse_log(log_path: Path) -> dict:
    """Extract what we can from a .md log file."""
    out = {
        "latency_ms_list": [],       # every latencyMs value found
        "tables_selected": None,     # TableSelector final count
        "complexity": None,          # complexity label found in JSON response
        "model": None,               # model_name from ResponseMetadata
        "iteration_count": 0,        # number of SQLBuilder calls
        "critic_rejections": 0,      # number of critic PASS=False responses
        "exec_errors": [],           # list of ERROR lines
        "start_ts": None,            # first timestamp
        "end_ts": None,              # last timestamp
        "tok_in": 0,
        "tok_out": 0,
    }

    if not log_path.exists():
        return out

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return out

    lines = text.splitlines()

    # Timestamps from lines like "[2026-04-24 19:24:51] [INFO]..."
    ts_pat = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
    timestamps = ts_pat.findall(text)
    if timestamps:
        out["start_ts"] = timestamps[0]
        out["end_ts"]   = timestamps[-1]

    # latencyMs from ResponseMetadata JSON blobs
    for m in re.finditer(r'"latencyMs":\s*\[(\d+)\]', text):
        out["latency_ms_list"].append(int(m.group(1)))

    # model name
    m_model = re.search(r'"model_name":\s*"([^"]+)"', text)
    if m_model:
        out["model"] = m_model.group(1)

    # tables selected
    m_tables = re.search(r"Total tables selected:\s*(\d+)", text, re.IGNORECASE)
    if m_tables:
        out["tables_selected"] = int(m_tables.group(1))

    # complexity from table_selector response JSON
    m_comp = re.search(r'"complexity":\s*"(LOW|MEDIUM|HIGH)"', text, re.IGNORECASE)
    if m_comp:
        out["complexity"] = m_comp.group(1).upper()

    # iteration count = number of SQLBuilder LLM calls
    out["iteration_count"] = len(re.findall(r"STAGE: LLM REQUEST: SQLBUILDER", text, re.IGNORECASE))

    # critic rejections = number of is_valid: false patterns
    out["critic_rejections"] = len(re.findall(r'"is_valid":\s*false', text, re.IGNORECASE))

    # execution errors
    error_lines = [l for l in lines if "[ERROR]" in l and "Pipeline" not in l]
    out["exec_errors"] = error_lines

    # token usage approximation from inputTokens / outputTokens
    for m in re.finditer(r'"inputTokens":\s*(\d+)', text):
        out["tok_in"] += int(m.group(1))
    for m in re.finditer(r'"outputTokens":\s*(\d+)', text):
        out["tok_out"] += int(m.group(1))

    return out


def _parse_csv_result(csv_path: Path) -> dict:
    """Read result CSV for rows, cols, and has_meaningful_data."""
    out = {"rows": 0, "cols": 0, "has_data": 0}
    if not csv_path.exists():
        return out
    try:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header:
                out["cols"] = len(header)
            meaningless = {"", '""', "none", "null", "[]", "{}", "nan", "undefined"}
            data_rows = 0
            for row in reader:
                if any(c.strip().lower() not in meaningless for c in row):
                    data_rows += 1
            out["rows"] = data_rows
            out["has_data"] = 1 if data_rows >= 1 else 0
    except Exception:
        pass
    return out


def _load_schema(db_name: str) -> dict:
    """Load cached schema JSON if available."""
    schema_path = METADATA_DIR / f"{db_name}.json"
    if schema_path.exists():
        try:
            with open(schema_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ────────────────────────────────────────────────────────────────────────────────
# Dataset index builder
# ────────────────────────────────────────────────────────────────────────────────

def _build_instance_index() -> dict[str, dict]:
    """Return {instance_id: {question, db, external_knowledge, dialect}} from all jsonl files."""
    index: dict[str, dict] = {}
    dialect_map = {
        "spider2-lite-sqlite.jsonl":    "sqlite",
        "spider2-lite-bigquery.jsonl":  "bigquery",
        "spider2-lite-snowflake.jsonl": "snowflake",
        "spider2-lite.jsonl":           "sqlite",
    }
    for fname, dialect in dialect_map.items():
        fpath = DATA_DIR / fname
        if not fpath.exists():
            continue
        with open(fpath, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    iid = item.get("instance_id")
                    if iid and iid not in index:
                        index[iid] = {
                            "question":           item.get("question", ""),
                            "db":                 item.get("db", ""),
                            "external_knowledge": item.get("external_knowledge"),
                            "dialect":            dialect,
                        }
                except Exception:
                    pass
    return index


# ────────────────────────────────────────────────────────────────────────────────
# Per-instance processing
# ────────────────────────────────────────────────────────────────────────────────

def _process_instance(
    db_dir:   Path,
    db_name:  str,
    iid:      str,
    meta:     dict,
    schema:   dict,
) -> dict:
    """Build a metrics row from available files for one instance."""

    sql_path = db_dir / f"{iid}.sql"
    csv_path = db_dir / f"{iid}.csv"
    log_path = db_dir / f"{iid}.md"

    # ── SQL ───────────────────────────────────────────────────────────────────
    final_sql = ""
    if sql_path.exists():
        try:
            final_sql = sql_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            pass

    # ── Result CSV ────────────────────────────────────────────────────────────
    csv_info = _parse_csv_result(csv_path)

    # ── Log ───────────────────────────────────────────────────────────────────
    log = _parse_log(log_path)

    # ── Question ──────────────────────────────────────────────────────────────
    question = meta.get("question", "")
    ext_know = meta.get("external_knowledge")
    dialect  = meta.get("dialect", "sqlite")

    # ── Outcome ───────────────────────────────────────────────────────────────
    if not sql_path.exists() and not csv_path.exists():
        pipeline_status = "ERROR"
    elif csv_info["has_data"]:
        pipeline_status = "SUCCESS"
    else:
        pipeline_status = "FAILED"

    is_fatal = 1 if pipeline_status == "ERROR" else 0

    # ── Timing from log ───────────────────────────────────────────────────────
    pipeline_duration_s = 0.0
    if log["start_ts"] and log["end_ts"]:
        try:
            fmt = "%Y-%m-%d %H:%M:%S"
            t0 = datetime.strptime(log["start_ts"], fmt)
            t1 = datetime.strptime(log["end_ts"],   fmt)
            pipeline_duration_s = round((t1 - t0).total_seconds(), 1)
        except Exception:
            pass

    # sum all latencyMs from log as rough LLM time
    total_latency_ms = sum(log["latency_ms_list"])
    llm_time_est = round(total_latency_ms / 1000, 3)

    # ── Schema ────────────────────────────────────────────────────────────────
    db_tables  = len(schema)
    fk_dens    = _fk_density(schema)
    schema_sz  = _total_columns(schema)
    tables_sel = log["tables_selected"] if log["tables_selected"] is not None else db_tables

    cov_ratio  = round(tables_sel / db_tables, 4) if db_tables else 0.0
    # schema cache: was there a cached metadata file?
    cache_hit  = 1 if (METADATA_DIR / f"{db_name}.json").exists() else 0

    # ── Question analysis ─────────────────────────────────────────────────────
    question_type = _classify_question(question, [])
    complexity    = log["complexity"] or "MEDIUM"

    # ── SQL Structural ────────────────────────────────────────────────────────
    sql_complexity   = _sql_complexity(final_sql)
    sql_joins        = _join_count(final_sql)
    sql_cte          = _kw(final_sql, "WITH")
    sql_window       = 1 if re.search(r"\bOVER\s*\(", final_sql, re.IGNORECASE) else 0
    sql_subq         = 1 if re.search(r"\(\s*SELECT\b", final_sql, re.IGNORECASE) else 0
    sql_agg          = _kw(final_sql, "SUM", "COUNT", "AVG", "MIN", "MAX")
    sql_case         = _kw(final_sql, "CASE")
    sql_lines        = len(final_sql.splitlines())

    iter_count       = max(log["iteration_count"], 1)
    critic_rej       = log["critic_rejections"]
    exec_errors      = log["exec_errors"]

    # ── Error classification ──────────────────────────────────────────────────
    last_err = exec_errors[-1][:300] if exec_errors else ""
    msg = last_err.lower()
    if   pipeline_status == "SUCCESS":       failure_stage, error_cat = "none", "none"
    elif pipeline_status == "ERROR":         failure_stage, error_cat = "fatal", "fatal_crash"
    elif "syntax" in msg or "parse" in msg:  failure_stage, error_cat = "execution", "syntax_error"
    elif "no such table" in msg:             failure_stage, error_cat = "execution", "schema_mismatch"
    elif "timeout" in msg:                   failure_stage, error_cat = "execution", "timeout"
    elif exec_errors:                        failure_stage, error_cat = "execution", "runtime_error"
    elif critic_rej > 0:                     failure_stage, error_cat = "generation", "critic_rejected"
    else:                                    failure_stage, error_cat = "execution", "empty_result"

    # ── Tokens & Cost ─────────────────────────────────────────────────────────
    tok_in  = log["tok_in"]
    tok_out = log["tok_out"]
    tok_tot = tok_in + tok_out
    model   = log["model"] or "unknown"
    cost    = _model_cost(model, tok_in, tok_out)
    cost_row = round(cost / csv_info["rows"], 6) if csv_info["rows"] > 0 else 0.0

    # ── Timestamp ─────────────────────────────────────────────────────────────
    timestamp = ""
    if log["end_ts"]:
        try:
            dt = datetime.strptime(log["end_ts"], "%Y-%m-%d %H:%M:%S")
            timestamp = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            timestamp = log["end_ts"]
    if not timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "id":           iid,
        "db":           db_name,
        "dialect":      dialect,
        "model":        model,
        "ts":           timestamp,

        "status":       pipeline_status,
        "rows_out":     csv_info["rows"],
        "cols_out":     csv_info["cols"],
        "has_data":     csv_info["has_data"],

        "duration_s":   pipeline_duration_s,
        "exec_ms":      0.0,
        "llm_s":        llm_time_est,

        "q_type":       question_type,
        "q_lvl":        complexity,
        "ext_kb":       1 if ext_know else 0,

        "db_tables":    db_tables,
        "fk_density":   fk_dens,
        "schema_cols":  schema_sz,
        "tbl_used":     tables_sel,
        "tbl_cov":      cov_ratio,
        "cache_hit":    cache_hit,

        "iters":        iter_count,
        "first_pass":   1 if iter_count <= 1 else 0,
        "retried":      1 if iter_count > 1 else 0,
        "critic_rej":   critic_rej,
        "exec_errs":    len(exec_errors),
        "sql_approach": "",

        "sql_score":    sql_complexity,
        "joins":        sql_joins,
        "has_cte":      sql_cte,
        "has_wfn":      sql_window,
        "has_subq":     sql_subq,
        "has_agg":      sql_agg,
        "has_case":     sql_case,
        "sql_lines":    sql_lines,

        "fail_stage":   failure_stage,
        "err_cat":      error_cat,
        "err_msg":      last_err,

        "tok_in":       tok_in,
        "tok_out":      tok_out,
        "tok_total":    tok_tot,
        "cost_usd":     cost,
        "cost_per_row": cost_row,
    }


# ────────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Backfill pipeline_metrics.csv from existing results")
    parser.add_argument("--db", type=str, default=None, help="Only process this DB folder (optional)")
    parser.add_argument("--overwrite", action="store_true", help="Re-process instances already in the CSV")
    args = parser.parse_args()

    print("[*] Loading instance index from JSONL files...")
    idx = _build_instance_index()
    print(f"    Loaded {len(idx)} instance definitions.")

    print(f"   Scanning for existing metrics files per DB...")

    # Determine which DB folders to scan
    db_dirs = []
    for d in sorted(RESULTS_BASE_DIR.iterdir()):
        if not d.is_dir():
            continue
        if args.db and d.name != args.db:
            continue
        db_dirs.append(d)

    print(f"[*] Scanning {len(db_dirs)} DB folders...\n")

    total_processed = 0
    total_skipped   = 0

    for db_dir in db_dirs:
        db_name = db_dir.name
        schema  = _load_schema(db_name)

        # Collect instance IDs from SQL files (most reliable indicator)
        iids = sorted(set(
            f.stem for f in db_dir.iterdir()
            if f.suffix == ".sql" and f.is_file()
        ))

        if not iids:
            # fallback: check CSV files
            iids = sorted(set(
                f.stem for f in db_dir.iterdir()
                if f.suffix == ".csv" and f.is_file()
            ))

        if not iids:
            continue

        print(f"  [{db_name}] {len(iids)} instances", end="", flush=True)

        db_count = 0

        # Load existing entries for this DB only
        db_metrics_path = _metrics_path(db_name)
        existing_db = _load_existing(db_metrics_path)

        for iid in iids:
            if iid in existing_db and not args.overwrite:
                total_skipped += 1
                continue

            meta = idx.get(iid, {"question": "", "db": db_name, "external_knowledge": None, "dialect": "sqlite"})
            row  = _process_instance(db_dir, db_name, iid, meta, schema)
            existing_db[iid] = row
            db_count    += 1
            total_processed += 1

        if db_count:
            _ensure_header(db_metrics_path)
            with open(db_metrics_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(existing_db.values())
            print(f" -> {db_count} written  [{db_metrics_path.name}]")
        else:
            print(" -> all skipped")

    print(f"[DONE] {total_processed} rows written, {total_skipped} skipped (use --overwrite to redo).")
    print(f"       Output: results/<db_name>/metrics.csv  (one file per DB)")


if __name__ == "__main__":
    main()
