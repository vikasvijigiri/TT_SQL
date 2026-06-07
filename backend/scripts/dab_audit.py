"""
dab_audit.py
------------
Comprehensive per-query audit report for DataAgentBench evaluation.

Usage:
    python backend/scripts/dab_audit.py
    python backend/scripts/dab_audit.py --out results/dab/full_audit_report.txt
"""

import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ── Constants ────────────────────────────────────────────────────────────────

RESULTS_DIR = ROOT_DIR / "backend" / "results" / "dab"
CONFIG_PATH = ROOT_DIR / "backend" / "config" / "system_params.yaml"
from backend.app.core.config import DAB_REPO

# Canonical 12 official datasets (lowercase keys used in results/)
OFFICIAL_DATASETS = [
    "agnews",
    "bookreview",
    "crmarenapro",
    "deps_dev_v1",
    "github_repos",
    "googlelocal",
    "music_brainz_20k",
    "pancancer_atlas",
    "patents",
    "stockindex",
    "stockmarket",
    "yelp",
]

# Query counts per dataset (from DAB README)
DATASET_QUERY_COUNTS = {
    "agnews": 4,
    "bookreview": 3,
    "crmarenapro": 13,
    "deps_dev_v1": 2,
    "github_repos": 4,
    "googlelocal": 4,
    "music_brainz_20k": 3,
    "pancancer_atlas": 3,
    "patents": 3,
    "stockindex": 3,
    "stockmarket": 5,
    "yelp": 7,
}

# DBMS used per dataset (from DAB README table)
DATASET_DBMS = {
    "agnews":           "MongoDB, SQLite",
    "bookreview":       "PostgreSQL, SQLite",
    "crmarenapro":      "DuckDB, PostgreSQL, SQLite",
    "deps_dev_v1":      "DuckDB, SQLite",
    "github_repos":     "DuckDB, SQLite",
    "googlelocal":      "PostgreSQL, SQLite",
    "music_brainz_20k": "DuckDB, SQLite",
    "pancancer_atlas":  "DuckDB, PostgreSQL",
    "patents":          "PostgreSQL, SQLite",
    "stockindex":       "DuckDB, SQLite",
    "stockmarket":      "DuckDB, SQLite",
    "yelp":             "DuckDB, MongoDB",
}


# ── Config loader ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not HAS_YAML or not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


# ── Eval result loader ────────────────────────────────────────────────────────

def load_eval(dataset: str, qid: int) -> dict | None:
    path = RESULTS_DIR / dataset / f"query{qid}_eval.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_query_text(dataset: str, qid: int) -> str:
    """Try to read query question from DAB repo."""
    ds_upper_map = {
        "deps_dev_v1": "DEPS_DEV_V1",
        "github_repos": "GITHUB_REPOS",
        "pancancer_atlas": "PANCANCER_ATLAS",
        "patents": "PATENTS",
    }
    ds_dir = ds_upper_map.get(dataset, dataset)
    q_json = DAB_REPO / f"query_{ds_dir}" / f"query{qid}" / "query.json"
    if not q_json.exists():
        # Try lowercase
        q_json = DAB_REPO / f"query_{dataset}" / f"query{qid}" / "query.json"
    if q_json.exists():
        try:
            with open(q_json, encoding="utf-8") as f:
                txt = json.load(f)
            if isinstance(txt, str):
                return txt.strip()
            if isinstance(txt, dict):
                return (txt.get("query") or txt.get("question") or "").strip()
        except Exception:
            pass
    return ""


# ── Failure categoriser ───────────────────────────────────────────────────────

def categorise_failure(reason: str) -> str:
    if not reason:
        return "Unknown"
    r = reason.lower()
    if "no csv" in r or "no result" in r or "empty" in r or "no data" in r:
        return "No CSV / Empty Result"
    if "error" in r and ("sql" in r or "execut" in r or "syntax" in r):
        return "SQL Execution Error"
    if "not found" in r or "missing" in r or "no match" in r or "not in" in r:
        return "Missing Entity / String Match"
    if any(x in r for x in ["wrong value", "expected", "mismatch", "incorrect", "got "]):
        return "Wrong Value"
    if "validate.py execution error" in r:
        return "Validator Error"
    if "fuzzy" in r or "edit" in r:
        return "Fuzzy Match Failure"
    return "Other"


# ── Formatting helpers ────────────────────────────────────────────────────────

W = 120  # report width

def hr(char="-", w=W):
    return char * w

def trunc(s: str, n: int) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").replace("\r", " ")
    return s[:n] + "..." if len(s) > n else s


# ── Main report builder ───────────────────────────────────────────────────────

def build_report(out_path: Path | None = None) -> None:
    cfg = load_config()
    llm_cfg = cfg.get("llm", {})
    orch_cfg = cfg.get("orchestrator", {})

    model       = llm_cfg.get("model", "bedrock/openai.gpt-oss-safeguard-120b")
    temperature = llm_cfg.get("temperature", 0)
    max_retries = orch_cfg.get("max_retries", 4)
    prune_tok   = orch_cfg.get("pruning_threshold_tokens", 3500)

    lines = []

    def p(*args):
        line = " ".join(str(a) for a in args)
        lines.append(line)
        print(line)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    p(hr("="))
    p("  DataAgentBench - Full Evaluation Audit Report")
    p(hr("="))
    p(f"  Generated     : {now}")
    p(f"  Model         : {model}")
    p(f"  Provider      : AWS Bedrock  (us-east-1)")
    p(f"  Temperature   : {temperature}")
    p(f"  Max Retries   : {max_retries}")
    p(f"  Prune Tokens  : {prune_tok}")
    p(f"  Pipeline      : SemanticDINOrchestrator (TT_SQL_V2)")
    p(f"  DAB Version   : 12 datasets / 54 queries")
    p(hr("="))

    # ── Collect all query results ─────────────────────────────────────────────
    all_rows = []
    total_pass = 0
    total_fail = 0
    total_pend = 0
    total_time = 0.0
    total_in_tok = 0
    total_out_tok = 0

    per_ds: dict[str, dict] = {}

    for ds in OFFICIAL_DATASETS:
        n_q = DATASET_QUERY_COUNTS[ds]
        per_ds[ds] = {"pass": 0, "fail": 0, "pend": 0, "total": n_q, "time": 0.0, "in_tok": 0, "out_tok": 0}

        for qid in range(1, n_q + 1):
            ev = load_eval(ds, qid)
            q_text = load_query_text(ds, qid)

            if ev is None:
                status   = "PENDING"
                passed   = None
                reason   = "-"
                gt       = ""
                answer   = ""
                elapsed  = None
                in_tok   = None
                out_tok  = None
                method   = "-"
                total_pend += 1
                per_ds[ds]["pend"] += 1
            else:
                passed  = ev.get("passed", False)
                status  = "PASS" if passed else "FAIL"
                reason  = ev.get("reason", "")
                gt      = ev.get("ground_truth", "")
                answer  = ev.get("agent_answer_snippet", "")
                elapsed = ev.get("elapsed_s")
                in_tok  = ev.get("input_tokens")
                out_tok = ev.get("output_tokens")
                method  = ev.get("method", "dynamic_validate_py")
                if passed:
                    total_pass += 1
                    per_ds[ds]["pass"] += 1
                else:
                    total_fail += 1
                    per_ds[ds]["fail"] += 1
                if elapsed:
                    total_time += elapsed
                    per_ds[ds]["time"] += elapsed
                if in_tok:
                    total_in_tok += in_tok
                    per_ds[ds]["in_tok"] += in_tok
                if out_tok:
                    total_out_tok += out_tok
                    per_ds[ds]["out_tok"] += out_tok

            all_rows.append({
                "dataset": ds,
                "qid": qid,
                "status": status,
                "passed": passed,
                "reason": reason,
                "gt": gt,
                "answer": answer,
                "elapsed": elapsed,
                "in_tok": in_tok,
                "out_tok": out_tok,
                "method": method,
                "q_text": q_text,
                "category": categorise_failure(reason) if status == "FAIL" else ("-" if status == "PASS" else "Pending"),
            })

    evaluated = total_pass + total_fail
    pass_at_1 = total_pass / evaluated if evaluated > 0 else 0.0
    avg_time  = total_time / evaluated if evaluated > 0 else 0.0

    # -- Per-query table -------------------------------------------------------
    p()
    p(hr())
    p("  PER-QUERY DIAGNOSIS TABLE")
    p(hr())

    hdr = f"  {'Dataset':<20} {'Q':>2}  {'Status':<7} {'Time':>7}  {'InTok':>6}  {'OutTok':>6}  {'Reason'}"
    p(hdr)
    p(hr())

    prev_ds = None
    for row in all_rows:
        ds  = row["dataset"]
        qid = row["qid"]
        st  = row["status"]
        el  = f"{row['elapsed']:.1f}s" if row["elapsed"] is not None else "     -"
        it  = str(row["in_tok"]) if row["in_tok"] is not None else "-"
        ot  = str(row["out_tok"]) if row["out_tok"] is not None else "-"
        rs  = trunc(row["reason"], 60)

        if ds != prev_ds:
            p()
            prev_ds = ds

        p(f"  {ds:<20} {qid:>2}  {st:<7} {el:>7}  {it:>6}  {ot:>6}  {rs}")

    p()
    p(hr())

    # -- Per-dataset summary --------------------------------------------------
    p()
    p(hr())
    p("  PER-DATASET ACCURACY SUMMARY")
    p(hr())
    hdr2 = f"  {'Dataset':<22} {'DBMS':<30} {'Total':>5}  {'Pass':>4}  {'Fail':>4}  {'Pend':>4}  {'Acc':>6}"
    p(hdr2)
    p(hr())

    for ds in OFFICIAL_DATASETS:
        d   = per_ds[ds]
        tot = d["total"]
        pa  = d["pass"]
        fa  = d["fail"]
        pe  = d["pend"]
        ev2 = tot - pe
        acc = f"{100*pa/ev2:.0f}%" if ev2 > 0 else "—"
        dbms_str = DATASET_DBMS.get(ds, "")
        p(f"  {ds:<22} {dbms_str:<30} {tot:>5}  {pa:>4}  {fa:>4}  {pe:>4}  {acc:>6}")

    p(hr())
    p(f"  {'OVERALL':<22} {'':30} {evaluated+total_pend:>5}  {total_pass:>4}  {total_fail:>4}  {total_pend:>4}  {pass_at_1*100:.1f}%")
    p(hr())

    # -- Failure digest -------------------------------------------------------
    p()
    p(hr())
    p("  FAILURE DIGEST - Grouped by Root Cause")
    p(hr())

    fail_rows = [r for r in all_rows if r["status"] == "FAIL"]
    pend_rows = [r for r in all_rows if r["status"] == "PENDING"]

    categories = {}
    for r in fail_rows:
        cat = r["category"]
        categories.setdefault(cat, []).append(r)

    for cat, rows in sorted(categories.items()):
        p()
        p(f"  [{cat}]  ({len(rows)} queries)")
        p(f"  {'Dataset':<22} {'Q':>2}  {'Ground Truth (truncated)':<45}  {'Reason'}")
        p("  " + "-" * (W - 2))
        for r in rows:
            gt_t = trunc(r["gt"], 45)
            rs_t = trunc(r["reason"], 55)
            p(f"  {r['dataset']:<22} {r['qid']:>2}  {gt_t:<45}  {rs_t}")

    if pend_rows:
        p()
        p(f"  [Pending - Not Yet Evaluated]  ({len(pend_rows)} queries)")
        p(f"  {'Dataset':<22} {'Q':>2}  {'Question (from query.json)'}")
        p("  " + "-" * (W - 2))
        for r in pend_rows:
            qt = trunc(r["q_text"], 80) or "-"
            p(f"  {r['dataset']:<22} {r['qid']:>2}  {qt}")

    # -- Resource metrics -----------------------------------------------------
    p()
    p(hr())
    p("  RESOURCE METRICS")
    p(hr())
    p(f"  Queries evaluated      : {evaluated} / {evaluated + total_pend}")
    p(f"  Queries passed         : {total_pass}")
    p(f"  Queries failed         : {total_fail}")
    p(f"  Queries pending        : {total_pend}")
    p(f"  Pass@1 (evaluated)     : {pass_at_1*100:.1f}%")
    p(f"  Pass@1 (all 54)        : {total_pass/(evaluated+total_pend)*100:.1f}%  (pending = failed)")
    p(f"  Total wall-clock time  : {total_time:.1f}s  ({total_time/60:.1f} min)")
    p(f"  Avg time / query       : {avg_time:.1f}s")
    p(f"  Total input tokens     : {total_in_tok:,}")
    p(f"  Total output tokens    : {total_out_tok:,}")
    p(f"  Total tokens           : {total_in_tok + total_out_tok:,}")
    p(hr("="))
    p("  END OF AUDIT REPORT")
    p(hr("="))

    # ── Save to file if requested ─────────────────────────────────────────────
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\n  Report saved -> {out_path}")


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="DataAgentBench full audit report")
    parser.add_argument("--out", type=str, default=None, help="Optional path to save report text file")
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else RESULTS_DIR / "full_audit_report.txt"
    build_report(out_path=out_path)
