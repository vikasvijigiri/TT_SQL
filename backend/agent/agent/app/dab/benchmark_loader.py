import typing
"""
benchmark_loader.py
-------------------
Crawls the cloned DataAgentBench repository and loads all 54 queries into
a unified list suitable for SpiderDIN processing.

Expected DAB repo layout:
  DataAgentBench/
    query_{dataset}/
      db_config.yaml       <- DB connections (SQLite, DuckDB, Postgres, Mongo)
      db_description.txt   <- Schema description
      db_description_withhint.txt
      query{N}/
        query.json         <- The question text (plain string JSON)
        ground_truth.csv   <- Expected answer value
        validate.py        <- Grading function: validate(llm_output) -> (bool, str)
      query_dataset/       <- Actual DB files (.sqlite, .duckdb, .sql dumps)
"""

import json
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
import contextlib


# Canonical DAB dataset list (matches run_agent.py DATASET_LIST)
DAB_DATASETS = [
    "bookreview",
    "crmarenapro",
    "DEPS_DEV_V1",
    "GITHUB_REPOS",
    "googlelocal",
    "PANCANCER_ATLAS",
    "PATENTS",
    "stockindex",
    "stockmarket",
    "yelp",
    "agnews",
    "music_brainz_20k",
    # Omitted/unofficial datasets commented out per user request:
    # "civic_unstructured",
    # "cve",
    # "imdb",
    # "krama",
    # "usaspending",
]

# DBMS support flags (True = supported without Docker)
DBMS_NO_DOCKER = {"sqlite", "duckdb"}
DBMS_NEEDS_DOCKER = {"postgres", "postgresql", "mongo", "mongodb"}


def _load_db_config(config_path: Path) -> Dict[str, Any]:
    """Load and parse a db_config.yaml file."""
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("db_clients", {})
    except Exception:
        return {}


def _load_query_text(query_dir: Path) -> Optional[str]:
    """Load query text from query.json (plain string or dict with 'question' key)."""
    query_file = query_dir / "query.json"
    if not query_file.exists():
        return None
    try:
        with open(query_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
        # The file may be a plain JSON string or a dict
        data = json.loads(content)
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            return data.get("question") or data.get("query") or str(data)
        return str(data)
    except Exception:
        # Fallback: treat raw content as question text
        try:
            with open(query_file, "r", encoding="utf-8") as f:
                return f.read().strip().strip('"')
        except Exception:
            return None


def _load_ground_truth(query_dir: Path) -> Optional[str]:
    """Load expected answer from ground_truth.csv."""
    gt_file = query_dir / "ground_truth.csv"
    if not gt_file.exists():
        return None
    try:
        with open(gt_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def _load_validate_source(query_dir: Path) -> Optional[str]:
    """Load validate.py source for grading."""
    vf = query_dir / "validate.py"
    if not vf.exists():
        return None
    try:
        with open(vf, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _resolve_db_paths(
    db_clients: Dict[str, Any], query_dataset_dir: Path
) -> Dict[str, Any]:
    """
    Resolve relative DB paths in db_config to absolute paths,
    and classify each DB by type.
    Returns enriched db_clients dict.
    """
    resolved = {}
    for name, cfg in db_clients.items():
        db_type = str(cfg.get("db_type", "")).lower()
        entry = {
            "name": name,
            "db_type": db_type,
            "needs_docker": db_type in DBMS_NEEDS_DOCKER,
        }

        # Resolve file-based DBs
        rel_path = cfg.get("db_path") or cfg.get("sql_file") or cfg.get("dump_folder")
        if rel_path:
            abs_path = (query_dataset_dir / rel_path).resolve()
            entry["db_path"] = str(abs_path)

        # For postgres / mongo: store connection metadata
        if db_type in ("postgres", "postgresql"):
            entry["db_name"] = cfg.get("db_name", name)
        elif db_type in ("mongo", "mongodb"):
            entry["db_name"] = cfg.get("db_name", name)
            entry["dump_folder"] = cfg.get("dump_folder", "")

        resolved[name] = entry
    return resolved


def load_all_queries(dab_repo_path: str) -> List[Dict[str, Any]]:
    """
    Crawl the DataAgentBench repository and return a list of all query dicts.

    Each dict contains:
      dataset      : str  (e.g. "bookreview")
      query_id     : str  (e.g. "1")
      instance_id  : str  (e.g. "bookreview_q1")
      question     : str  (natural language question)
      ground_truth : str  (expected answer)
      db_clients   : dict (resolved DB connections)
      validate_src : str  (source of validate.py)
      needs_docker : bool (True if any DB needs Docker)
      query_dir    : str  (absolute path to query folder)
      dataset_dir  : str  (absolute path to dataset folder)
      has_hint     : bool (db_description_withhint.txt exists)
      db_description: str (schema description text)
    """
    dab_root = Path(dab_repo_path)
    if not dab_root.exists():
        raise FileNotFoundError(f"DataAgentBench repo not found at: {dab_repo_path}")

    queries = []

    for dataset in DAB_DATASETS:
        dataset_lower = dataset.lower()
        # Directory is prefixed with "query_"
        dataset_dir = dab_root / f"query_{dataset_lower}"
        if not dataset_dir.exists():
            # Try original casing
            dataset_dir = dab_root / f"query_{dataset}"
            if not dataset_dir.exists():
                continue

        db_config_path = dataset_dir / "db_config.yaml"
        db_clients_raw = _load_db_config(db_config_path)
        dataset_dir / "query_dataset"

        # Resolve DB paths
        db_clients = _resolve_db_paths(db_clients_raw, dataset_dir)
        any_docker = any(v.get("needs_docker", False) for v in db_clients.values())

        # Load schema description — use only the hint-free description.
        # db_description_withhint.txt contains ground-truth hints and MUST NOT
        # be fed into the inference pipeline.
        desc_file = dataset_dir / "db_description.txt"
        hint_file = dataset_dir / "db_description_withhint.txt"
        db_description = ""
        if desc_file.exists():
            with contextlib.suppress(Exception):
                db_description = desc_file.read_text(encoding="utf-8").strip()

        has_hint = hint_file.exists()

        # Find all query subdirectories (query1, query2, ...)
        for item in sorted(dataset_dir.iterdir()):
            if not item.is_dir():
                continue
            # Match query subdirs: query1, query2, etc.
            name = item.name
            if not (name.startswith("query") and name != "query_dataset"):
                continue
            query_id_str = name.replace("query", "").strip()
            if not query_id_str.isdigit():
                continue

            question = _load_query_text(item)
            ground_truth = _load_ground_truth(item)
            validate_src = _load_validate_source(item)

            if not question:
                continue

            instance_id = f"{dataset_lower}_q{query_id_str}"

            queries.append(
                {
                    "dataset": dataset_lower,
                    "query_id": query_id_str,
                    "instance_id": instance_id,
                    "question": question,
                    "ground_truth": ground_truth or "",
                    "db_clients": db_clients,
                    "validate_src": validate_src or "",
                    "needs_docker": any_docker,
                    "query_dir": str(item),
                    "dataset_dir": str(dataset_dir),
                    "has_hint": has_hint,
                    "db_description": db_description,
                }
            )

    # Sort by dataset, then query_id numerically
    queries.sort(key=lambda x: (x["dataset"], int(x["query_id"])))  # type: ignore
    return queries


def summarize_queries(queries: List[Dict[str, Any]]) -> None:
    """Print a summary of loaded queries."""
    total = len(queries)
    with_docker = sum(1 for q in queries if q["needs_docker"])
    no_docker = total - with_docker

    print(f"\n{'=' * 60}")
    print("  DataAgentBench - Query Index")
    print(f"{'=' * 60}")
    print(f"  Total queries : {total}")
    print(f"  No Docker     : {no_docker}")
    print(f"  Needs Docker  : {with_docker}")
    print(f"{'-' * 60}")

    datasets: dict[str, typing.Any] = {}
    for q in queries:
        ds = q["dataset"]
        datasets.setdefault(ds, []).append(q)

    for ds, qs in sorted(datasets.items()):
        docker_flag = "[D]" if any(q["needs_docker"] for q in qs) else "[L]"
        dbtypes = set()
        for q in qs:
            for cfg in q["db_clients"].values():
                dbtypes.add(cfg.get("db_type", "?"))
        print(
            f"  {docker_flag} {ds:<22} {len(qs):>2} queries  [{', '.join(sorted(dbtypes))}]"
        )
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    import sys
    from agent.app.core.config import DAB_REPO as _DAB_REPO

    repo = sys.argv[1] if len(sys.argv) > 1 else str(_DAB_REPO)
    qs = load_all_queries(repo)
    summarize_queries(qs)
    print(json.dumps(qs, indent=2, default=str)[:2000], "...")
