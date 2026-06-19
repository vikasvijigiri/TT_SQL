"""
Auto-extract schema JSON files for all DataAgentBench databases.

For every SQLite and DuckDB file in the DAB query directories, this script
introspects the live tables and writes one JSON file per table into the same
directory where the .db / .duckdb file lives.  This lets SemanticContextEngine
(which receives db_directory = parent of the db file) find the schema on the
next DAB run without any code changes.

JSON format matches the existing IPL schema files:
  {
    "table_name": "...",
    "table_fullname": "...",
    "column_names": [...],
    "column_types": [...],
    "sample_rows": [...],
    "description": [...]
  }

Run from the project root:
    python extract_dab_schemas.py
"""

import sys
import os
import json
import ast
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "agent"))

from agent.app.dab.benchmark_loader import load_all_queries
from agent.app.core.config import DAB_REPO

SAMPLE_ROWS = 5


def extract_sqlite_schema(db_path: str, out_dir: Path) -> int:
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=10)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in c.fetchall()]
    written = 0
    for table in tables:
        try:
            cols = c.execute(f'PRAGMA table_info("{table}")').fetchall()
            col_names = [col[1] for col in cols]
            col_types = [col[2].upper() if col[2] else "TEXT" for col in cols]
            rows = []
            try:
                raw = c.execute(f'SELECT * FROM "{table}" LIMIT {SAMPLE_ROWS}').fetchall()
                rows = [dict(zip(col_names, row)) for row in raw]
            except Exception:
                pass
            schema = {
                "table_name": table,
                "table_fullname": table,
                "column_names": col_names,
                "column_types": col_types,
                "sample_rows": rows,
                "description": [""] * len(col_names),
            }
            out_file = out_dir / f"{table}.json"
            out_file.write_text(json.dumps(schema, indent=2, default=str), encoding="utf-8")
            written += 1
        except Exception as e:
            print(f"    WARN: skipped table '{table}': {e}")
    conn.close()
    return written


def extract_duckdb_schema(db_path: str, out_dir: Path) -> int:
    try:
        import duckdb
    except ImportError:
        print("  SKIP (duckdb not installed)")
        return 0
    try:
        conn = duckdb.connect(db_path, read_only=True)
    except Exception as e:
        print(f"  SKIP (cannot open duckdb: {e})")
        return 0
    try:
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    except Exception as e:
        print(f"  SKIP (SHOW TABLES failed: {e})")
        conn.close()
        return 0

    written = 0
    for table in tables:
        try:
            schema_rows = conn.execute(f'DESCRIBE "{table}"').fetchall()
            col_names = [r[0] for r in schema_rows]
            col_types = [r[1].upper() if r[1] else "TEXT" for r in schema_rows]
            rows = []
            try:
                raw = conn.execute(f'SELECT * FROM "{table}" LIMIT {SAMPLE_ROWS}').fetchall()
                rows = [dict(zip(col_names, row)) for row in raw]
            except Exception:
                pass
            schema = {
                "table_name": table,
                "table_fullname": table,
                "column_names": col_names,
                "column_types": col_types,
                "sample_rows": rows,
                "description": [""] * len(col_names),
            }
            out_file = out_dir / f"{table}.json"
            out_file.write_text(json.dumps(schema, indent=2, default=str), encoding="utf-8")
            written += 1
        except Exception as e:
            print(f"    WARN: skipped table '{table}': {e}")
    conn.close()
    return written


def main():
    queries = load_all_queries(str(DAB_REPO))

    # Collect unique db_path -> db_type pairs (skip docker, skip already done)
    seen: dict[str, str] = {}
    for q in queries:
        try:
            clients = ast.literal_eval(q["db_clients"]) if isinstance(q["db_clients"], str) else q["db_clients"]
        except Exception:
            clients = {}
        for db_key, db_info in clients.items():
            db_path = db_info.get("db_path", "")
            db_type = db_info.get("db_type", "").lower()
            needs_docker = db_info.get("needs_docker", False)
            if not db_path or str(needs_docker).lower() == "true":
                continue
            if db_type not in ("sqlite", "duckdb"):
                continue
            if not Path(db_path).is_file():
                print(f"  MISSING file: {db_path}")
                continue
            if db_path not in seen:
                seen[db_path] = db_type

    total_files = 0
    total_tables = 0
    skipped = 0

    print(f"\nExtracting schemas for {len(seen)} database files ...\n")
    for db_path, db_type in sorted(seen.items()):
        out_dir = Path(db_path).parent
        db_short = Path(db_path).name
        # We only skip if all tables in this database already have their JSON files
        import sqlite3
        try:
            if db_type == "sqlite":
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                db_tables = [r[0] for r in c.fetchall()]
                conn.close()
            else:
                import duckdb
                conn = duckdb.connect(db_path, read_only=True)
                db_tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
                conn.close()
            
            if db_tables and all((out_dir / f"{t}.json").exists() for t in db_tables):
                print(f"  SKIP  {db_short} (all table JSON files already exist)")
                skipped += 1
                continue
        except Exception:
            pass
        print(f"  [{db_type.upper()}] {db_short}")
        print(f"         -> {out_dir}")
        try:
            if db_type == "sqlite":
                n = extract_sqlite_schema(db_path, out_dir)
            else:
                n = extract_duckdb_schema(db_path, out_dir)
            print(f"         -> wrote {n} table JSON files")
            total_files += 1
            total_tables += n
        except Exception as e:
            print(f"         -> ERROR: {e}")

    print(f"\n{'='*60}")
    print(f"  Done: {total_files} databases processed, {total_tables} table schemas written")
    print(f"  Skipped (already had JSON): {skipped}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
