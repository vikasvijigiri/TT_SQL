import typing

import os

import re

import json

import time

import yaml

from typing import List, Dict, Any, Optional

from agent.app.models.schemas import SemanticContext, SemanticTable, SemanticColumn

from agent.services.logger import logger

import contextlib





def _load_homogeneous_threshold(default: int = 8) -> int:

    """Read homogeneous_threshold from system_params.yaml; fall back to *default*."""

    try:

        here = os.path.dirname(__file__)

        params_path = os.path.normpath(os.path.join(here, "..", "..", "..", "config", "system_params.yaml"))

        with open(params_path, "r", encoding="utf-8") as f:

            params = yaml.safe_load(f) or {}

        return int(params.get("schema_engine", {}).get("homogeneous_threshold", default))

    except Exception:

        return default



_CONTEXT_CACHE: Dict[str, SemanticContext] = {}

_DISCOVERY_CACHE: Dict[tuple, List[str]] = {}





class SemanticContextEngine:

    # All dialect folder names that may appear in a resources/databases/{dialect}/ path.

    # This list is intentionally broad -- unknown names fall through to the positional

    # heuristic below so new dialects never break path parsing.

    _KNOWN_DIALECT_DIRS = {

        "snowflake",

        "bigquery",

        "sqlite",

        "duckdb",

        "postgresql",

        "postgres",

        "mysql",

        "mssql",

        "oracle",

        "mongodb",

        "trino",

        "redshift",

        "spark",

        "databricks",

        "hive",

        "databases",

    }



    def __init__(

        self,

        db_directory: str,

        max_sample_values: int = 15,

        silent: bool = False,

        db_name: str | None = None,

        schema_name: str | None = None,

    ):

        self.db_directory = os.path.normpath(db_directory)

        self.max_sample_values = max_sample_values

        self.silent = silent

        self.context: SemanticContext = None  # type: ignore

        # ISO-8601 timestamp of the last schema load; None until load_context() runs.

        self._schema_loaded_at: Optional[str] = None



        # Allow callers to pass explicit names (e.g. when constructed from a connection string).

        if db_name is not None:

            self.db_name = db_name

            self.schema_name = schema_name or ""

        else:

            # Derive DB.SCHEMA prefix from directory path.

            # Expected layout: .../databases/{dialect}/{DB}/{SCHEMA}/

            # Falls back to last-two-segments if no known dialect folder found.

            parts = self.db_directory.replace("\\", "/").split("/")

            dialect_idx = None

            for i, p in enumerate(parts):

                if p.lower() in self._KNOWN_DIALECT_DIRS:

                    dialect_idx = i

                    break

            if dialect_idx is not None and dialect_idx + 1 < len(parts):

                self.db_name = parts[dialect_idx + 1]

                self.schema_name = (

                    parts[dialect_idx + 2] if dialect_idx + 2 < len(parts) else ""

                )

            elif len(parts) >= 2:

                # Positional fallback: treat last two path segments as DB / SCHEMA

                self.db_name = parts[-2]

                self.schema_name = parts[-1]

            else:

                self.db_name = parts[-1] if parts else ""

                self.schema_name = ""



        self.fqn_prefix = (

            f"{self.db_name}.{self.schema_name}."

            if self.db_name and self.schema_name

            else ""

        )



    def _sanitize_sample_values(self, raw_samples: List[Any]) -> List[str]:

        cleaned = []

        for val in raw_samples:

            if val is None:

                continue

            val_str = str(val).strip()

            # Skip empty strings, huge text, or JSON objects/arrays

            if (

                not val_str

                or (val_str.startswith("{") and val_str.endswith("}"))

                or (val_str.startswith("[") and val_str.endswith("]"))

            ):

                continue

            if len(val_str) > 300:

                val_str = val_str[:297] + "..."

            if val_str not in cleaned:

                cleaned.append(val_str)

        return cleaned[: self.max_sample_values]



    def build_context(self) -> SemanticContext:

        """Parses local JSON metadata files to build the Governed Semantic Context."""

        _cache_key = (self.db_directory, self.db_name, self.schema_name)

        if _cache_key in _CONTEXT_CACHE:

            self.context = _CONTEXT_CACHE[_cache_key]  # type: ignore

            return self.context



        if not self.silent:

            logger.info(f"Building Governed Semantic Context from: {self.db_directory}")

        tables: List[SemanticTable] = []



        if not os.path.exists(self.db_directory):

            logger.error(f"Directory not found: {self.db_directory}")

            return SemanticContext(tables=[])



        for root, _dirs, files in os.walk(self.db_directory):

            for filename in files:

                if not filename.endswith(".json"):

                    continue



                filepath = os.path.join(root, filename)

                table_name = filename.replace(".json", "")



                try:

                    with open(filepath, "r", encoding="utf-8") as f:

                        data = json.load(f)



                    columns: List[SemanticColumn] = []

                    sample_rows: List[dict] = []



                    # -- Format A: IDC-style ----------------------------------

                    if (

                        "columns" in data

                        and isinstance(data["columns"], list)

                        and data["columns"]

                        and isinstance(data["columns"][0], dict)

                    ):

                        samples = (

                            data.get("sample", [])

                            or data.get("all_samples", [])

                            or data.get("sample_rows", [])

                        )

                        if isinstance(samples, list):

                            sample_rows = [s for s in samples if isinstance(s, dict)]

                        for col_data in data["columns"]:

                            raw_samples = col_data.get("sample_values", [])

                            unique_samples = self._sanitize_sample_values(raw_samples)

                            columns.append(

                                SemanticColumn(

                                    name=col_data.get("column_name", ""),

                                    type=col_data.get("type", "UNKNOWN"),

                                    description=col_data.get("description", ""),

                                    sample_values=unique_samples,

                                )

                            )



                    # -- Format B: Spider2-style ------------------------------

                    elif "column_names" in data:

                        col_names = data.get("column_names", [])

                        col_types = data.get("column_types", [])

                        col_descs = data.get("description", [])

                        sample_rows = data.get("sample_rows", [])



                        # Discover nested keys for VARIANT/JSON columns

                        nested_map: dict[str, typing.Any] = {}

                        for row in sample_rows:

                            for col_name, val in row.items():

                                if isinstance(val, str) and (

                                    val.startswith("{") or val.startswith("[")

                                ):

                                    try:

                                        parsed = json.loads(val)

                                        keys = []

                                        if isinstance(parsed, dict):

                                            keys = list(parsed.keys())

                                        elif (

                                            isinstance(parsed, list)

                                            and len(parsed) > 0

                                            and isinstance(parsed[0], dict)

                                        ):

                                            keys = list(parsed[0].keys())

                                        if keys:

                                            if col_name not in nested_map:

                                                nested_map[col_name] = set()

                                            nested_map[col_name].update(keys)

                                    except Exception:

                                        pass



                        # Build per-column sample values from sample_rows.

                        # Cap each value at 300 chars to prevent large text columns

                        # (source code, git diffs) from bloating the prompt.

                        _MAX_SAMPLE_CHAR = 300

                        col_samples: dict = {n: [] for n in col_names}

                        for row in sample_rows:

                            for n in col_names:

                                val = row.get(n)

                                if val is not None:

                                    s = str(val)

                                    col_samples[n].append(s[:_MAX_SAMPLE_CHAR] if len(s) > _MAX_SAMPLE_CHAR else val)



                        for idx, col_name in enumerate(col_names):

                            col_type = (

                                col_types[idx] if idx < len(col_types) else "UNKNOWN"

                            )

                            col_desc = col_descs[idx] if idx < len(col_descs) else ""

                            unique_samples = self._sanitize_sample_values(

                                col_samples[col_name]

                            )

                            columns.append(

                                SemanticColumn(

                                    name=col_name,

                                    type=col_type,

                                    description=col_desc,

                                    sample_values=unique_samples,

                                    nested_keys=list(nested_map.get(col_name, [])),

                                )

                            )



                    foreign_keys = data.get("foreign_keys", [])

                    fk_strings = (

                        [str(fk) for fk in foreign_keys]

                        if isinstance(foreign_keys, list)

                        else []

                    )



                    schema_part = self.schema_name

                    if not schema_part:

                        rel_dir = os.path.relpath(root, self.db_directory).replace(

                            "\\", "/"

                        )

                        if rel_dir != "." and "/" not in rel_dir:

                            schema_part = rel_dir

                    prefix = (

                        f"{self.db_name}.{schema_part}."

                        if self.db_name and schema_part

                        else self.fqn_prefix

                    )



                    fqn = data.get("table_fullname") or (

                        f"{prefix}{table_name}" if prefix else table_name

                    )

                    table = SemanticTable(

                        name=fqn,

                        description=data.get(

                            "description", f"Table containing {table_name} data"

                        )

                        if isinstance(data.get("description"), str)

                        else f"Table containing {table_name} data",

                        columns=columns,

                        foreign_keys=fk_strings,

                        sample_rows=sample_rows[:2],

                    )

                    tables.append(table)

                    logger.debug(f"Parsed [{fqn}] -- {len(columns)} columns")



                except Exception as e:

                    logger.warning(f"Failed to parse {filename}: {e!s}")



        if not tables:

            tables = self._build_from_db_files()



        self.context = SemanticContext(tables=tables)  # type: ignore

        _CONTEXT_CACHE[_cache_key] = self.context

        self._schema_loaded_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if not self.silent:

            logger.success(f"Built Semantic Context with {len(tables)} tables (loaded at {self._schema_loaded_at}).")

        return self.context



    def format_for_prompt(

        self,

        relevant_tables: List[str] | None = None,

        table_columns: Dict[str, List[str]] | None = None,

        slim: bool = False,

        include_samples: bool = False,

    ) -> str:

        """Returns a highly compressed YAML-like string representation of the Semantic Context."""

        if not self.context:

            self.build_context()



        from agent.app.core.schema.schema_compressor import SchemaCompressor

        from agent.orchestration.pipeline_config import BALANCED_CONFIG



        is_sf = "snowflake" in self.db_directory.lower()

        compressor = SchemaCompressor(BALANCED_CONFIG)

        if slim:

            compressor.level = "aggressive"

        elif include_samples:

            compressor.level = "verbose"



        compressed_schema = compressor.compress_database_schema(

            context=self.context,

            is_sf=is_sf,

            relevant_tables=relevant_tables,

            table_columns=table_columns,

        )



        logger.debug(

            f"[SemanticEngine] Formatted prompt schema (~{len(compressed_schema) // 4} tokens)."

        )

        return compressed_schema



    def extract_join_graph(

        self, selected_tables: List[str], max_paths: int = 25

    ) -> str:

        """

        Return a compact FK/PK join-path block for the already-pruned selected tables.



        Token safety: always called AFTER schema linking, so selected_tables is 3-10 items.

        For 10 tables, C(10,2)=45 candidate pairs maximum -- output is always bounded.



        Two sources (in priority order):

        1. Structured FK declarations from table.foreign_keys metadata

        2. Heuristic: columns ending in `_id` whose prefix matches another selected table name



        Heuristic deliberately ignores plain `id` columns (they are primary keys, not FKs).

        """

        if not self.context or not self.context.tables:

            return ""



        # Build base-name => SemanticTable for selected tables only

        selected_bases = {

            t.lower().replace('"', "").split(".")[-1] for t in selected_tables

        }

        selected_objs: Dict[str, "SemanticTable"] = {}

        for t in self.context.tables:

            base = t.name.lower().replace('"', "").split(".")[-1]

            if base in selected_bases:

                selected_objs[base] = t



        if len(selected_objs) < 2:

            return ""



        paths: List[str] = []

        seen: set = set()



        # -- Source 1: explicit FK declarations -------------------------------

        _FK_RE = re.compile(

            r"FOREIGN KEY\s*\(([^)]+)\)\s*REFERENCES\s+([^\s(]+)\s*\(([^)]+)\)",

            re.IGNORECASE,

        )

        for base, table in selected_objs.items():

            for fk_str in table.foreign_keys or []:

                m = _FK_RE.match(fk_str)

                if not m:

                    continue

                src_col = m.group(1).strip().strip('"')

                ref_base = m.group(2).strip().strip('"').split(".")[-1].lower()

                ref_col = m.group(3).strip().strip('"')

                if ref_base in selected_objs:

                    key = (base, src_col.lower(), ref_base, ref_col.lower())

                    if key not in seen:

                        seen.add(key)

                        paths.append(f"{base}.{src_col} => {ref_base}.{ref_col}")



        # -- Source 2: heuristic *_id column matching -------------------------

        if len(paths) < max_paths:

            for base, table in selected_objs.items():

                for col in table.columns or []:

                    col_lower = col.name.lower().strip('"')

                    if not col_lower.endswith("_id") or col_lower == "id":

                        continue

                    prefix = col_lower[:-3]  # strip '_id' suffix

                    # Check singular, plural, and de-pluralised variants

                    for candidate in (

                        prefix,

                        prefix + "s",

                        prefix + "es",

                        prefix.rstrip("s"),

                    ):

                        if candidate not in selected_objs or candidate == base:

                            continue

                        ref_table = selected_objs[candidate]

                        # Prefer the ref table's own 'id' or '{candidate}_id' column as the PK

                        pk_col = "id"

                        for rc in ref_table.columns or []:

                            rc_lower = rc.name.lower().strip('"')

                            if rc_lower == "id" or rc_lower == f"{candidate}_id":

                                pk_col = rc.name

                                break

                        key = (base, col_lower, candidate, pk_col.lower())

                        if key not in seen and len(paths) < max_paths:

                            seen.add(key)

                            paths.append(f"{base}.{col.name} => {candidate}.{pk_col}")

                        break



        if not paths:

            return ""



        lines = ["[JOIN PATHS between selected tables]:"]

        lines.extend(f"  {p}" for p in paths[:max_paths])

        return "\n".join(lines)



    def discover_and_load_table(self, table_name: str) -> List[SemanticTable]:

        """Scans neighboring database directories under resources/databases/{dialect}

        for a table matching table_name (case-insensitively). Loads and registers it

        in the context.

        """

        # Determine dialect from current db_directory

        parts = self.db_directory.replace("\\", "/").split("/")

        try:

            dialect_idx = next(

                i

                for i, p in enumerate(parts)

                if p in ("snowflake", "bigquery", "sqlite")

            )

            parts[dialect_idx]

        except StopIteration:

            pass



        # Use resources/databases/{dialect} as search root

        base_dir = os.path.dirname(self.db_directory)

        if not os.path.exists(base_dir):

            return []



        search_term = table_name.lower().replace('"', "").replace("`", "").strip()

        if "." in search_term:

            search_term = search_term.split(".")[-1]



        if len(search_term) < 3:

            return []



        cache_key = (base_dir, search_term)

        if cache_key in _DISCOVERY_CACHE:

            matching_files = _DISCOVERY_CACHE[cache_key]

        else:

            import glob



            pattern = os.path.join(base_dir, "**", "*.json")

            matching_files = []

            for filepath in glob.glob(pattern, recursive=True):

                filename = os.path.basename(filepath)

                t_name = filename.replace(".json", "").lower()

                if search_term in t_name or t_name in search_term:

                    matching_files.append(filepath)

            _DISCOVERY_CACHE[cache_key] = matching_files



        loaded_tables = []

        for filepath in matching_files:

            # Check if already loaded in context

            rel_path = os.path.relpath(filepath, base_dir).replace("\\", "/")

            path_parts = rel_path.split("/")

            if len(path_parts) >= 3:

                db = path_parts[0].upper()

                schema = path_parts[1].upper()

                tbl = path_parts[2].replace(".json", "")

                fqn = f"{db}.{schema}.{tbl}"

            else:

                tbl = os.path.basename(filepath).replace(".json", "")

                fqn = tbl



            # Avoid duplicates

            if self.context and any(

                t.name.upper() == fqn.upper() for t in self.context.tables

            ):

                continue



            try:

                with open(filepath, "r", encoding="utf-8") as f:

                    data = json.load(f)



                columns: List[SemanticColumn] = []

                sample_rows = (

                    data.get("sample_rows", []) or data.get("sample", []) or []

                )



                # Format A / B parser logic

                if "columns" in data and isinstance(data["columns"], list):

                    for col_data in data["columns"]:

                        raw_samples = col_data.get("sample_values", [])

                        columns.append(

                            SemanticColumn(

                                name=col_data.get("column_name", ""),

                                type=col_data.get("type", "UNKNOWN"),

                                description=col_data.get("description", ""),

                                sample_values=self._sanitize_sample_values(raw_samples),

                            )

                        )

                elif "column_names" in data:

                    col_names = data.get("column_names", [])

                    col_types = data.get("column_types", [])

                    col_descs = data.get("description", [])  # type: ignore

                    col_samples = {n: [] for n in col_names}

                    for row in sample_rows:

                        if isinstance(row, dict):

                            for n in col_names:

                                val = row.get(n)

                                if val is not None:

                                    col_samples[n].append(val)



                    for idx, col_name in enumerate(col_names):

                        col_type = col_types[idx] if idx < len(col_types) else "UNKNOWN"

                        col_desc = col_descs[idx] if idx < len(col_descs) else ""

                        columns.append(

                            SemanticColumn(

                                name=col_name,

                                type=col_type,

                                description=col_desc,

                                sample_values=self._sanitize_sample_values(

                                    col_samples[col_name]

                                ),

                            )

                        )



                table_obj = SemanticTable(

                    name=fqn,

                    description=data.get("description", f"Table containing {tbl} data")

                    if isinstance(data.get("description"), str)

                    else f"Table containing {tbl} data",

                    columns=columns,

                    foreign_keys=[str(fk) for fk in data.get("foreign_keys", [])],

                    sample_rows=sample_rows[:2],

                )

                if not self.context:

                    self.context = SemanticContext(tables=[])

                self.context.tables.insert(0, table_obj)

                loaded_tables.append(table_obj)

                logger.info(

                    f"Dynamically discovered and loaded cross-database table: {fqn}"

                )

            except Exception as e:

                logger.warning(f"Failed to dynamically load {filepath}: {e}")



        return loaded_tables



    @staticmethod

    def _infer_column_hint(col_name: str, sample_vals: List[str]) -> str:

        """

        Return a parenthetical hint when sample values reveal the column's semantics

        differ from what the name suggests -- e.g. a column named `rating_number`

        whose values are large integers is clearly a review COUNT, not an average.



        Returns an empty string when no hint is warranted so the description stays clean.

        """

        if not sample_vals:

            return ""

        nums = []

        for v in sample_vals:

            with contextlib.suppress(ValueError, TypeError):

                nums.append(float(v))

        if not nums:

            return ""

        max_val = max(nums)

        col_lower = col_name.lower()

        # Large-integer column with a name that could be mistaken for a rating/score

        rating_words = {"rating", "score", "grade", "rank", "star"}

        count_words = {"count", "num", "number", "total", "qty", "amount", "n_"}

        looks_like_rating_name = any(w in col_lower for w in rating_words)

        looks_like_count_name = any(w in col_lower for w in count_words)

        if max_val > 100 and (looks_like_rating_name or looks_like_count_name):

            return " (NOTE: values are counts/totals, NOT a rating average)"

        return ""



    def _build_from_db_files(self) -> List[SemanticTable]:

        def is_sqlite_file(filepath: str) -> bool:

            try:

                if not os.path.exists(filepath) or os.path.isdir(filepath):

                    return False

                with open(filepath, "rb") as f:

                    header = f.read(16)

                    return header.startswith(b"SQLite format 3\x00")

            except Exception:

                return False



        tables = []

        import glob



        # 1. Look for SQLite files

        sqlite_files = []

        for ext in ("*.sqlite", "*.db", "*.sqlite3"):

            sqlite_files.extend(glob.glob(os.path.join(self.db_directory, ext)))

            sqlite_files.extend(

                glob.glob(os.path.join(self.db_directory, "**", ext), recursive=True)

            )

        sqlite_files = list(set(sqlite_files))

        sqlite_files = [f for f in sqlite_files if is_sqlite_file(f)]



        for db_file in sqlite_files:

            import sqlite3



            conn = None

            try:

                conn = sqlite3.connect(db_file)

                conn.row_factory = sqlite3.Row

                cursor = conn.cursor()

                # Get tables

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")

                table_names = [

                    r[0]

                    for r in cursor.fetchall()

                    if r[0] not in ("sqlite_sequence", "sqlite_stat1")

                ]



                for t_name in table_names:

                    # Get schema

                    cursor.execute(f'PRAGMA table_info("{t_name}");')

                    cols = cursor.fetchall()



                    # Get foreign keys

                    cursor.execute(f'PRAGMA foreign_key_list("{t_name}");')

                    fks = cursor.fetchall()

                    fk_strings = []

                    for fk in fks:

                        fk_strings.append(

                            f"FOREIGN KEY ({fk['from']}) REFERENCES {fk['table']}({fk['to']})"

                        )



                    columns = []

                    # Get sample rows

                    try:

                        cursor.execute(f'SELECT * FROM "{t_name}" LIMIT 100;')

                        sample_data = [dict(r) for r in cursor.fetchall()]

                    except Exception:

                        sample_data = []



                    for col in cols:

                        col_name = col["name"]

                        col_type = col["type"]



                        raw_samples = []

                        for row in sample_data:

                            val = row.get(col_name)

                            if val is not None:

                                raw_samples.append(val)



                        sample_vals = self._sanitize_sample_values(raw_samples)

                        hint = self._infer_column_hint(col_name, sample_vals)

                        columns.append(

                            SemanticColumn(

                                name=col_name,

                                type=col_type or "UNKNOWN",

                                description=f"Column '{col_name}' in table '{t_name}'{hint}",

                                sample_values=sample_vals,

                            )

                        )



                    # Use bare table name -- live SQLite/DuckDB files are accessed via

                    # ATTACH temp views which have no schema prefix in SQL.

                    empty_note = (

                        " (WARNING: table has 0 rows -- data may require an external service)"

                        if not sample_data

                        else ""

                    )

                    tables.append(

                        SemanticTable(

                            name=t_name,

                            description=f"Table '{t_name}' loaded from SQLite database{empty_note}",

                            columns=columns,

                            foreign_keys=fk_strings,

                            sample_rows=sample_data[:2],

                        )

                    )

            except Exception as e:

                logger.warning(

                    f"Failed to dynamically extract SQLite schema from {db_file}: {e}"

                )

            finally:

                if conn:

                    with contextlib.suppress(Exception):

                        conn.close()



        # 2. Look for DuckDB files

        duckdb_files = []

        for ext in ("*.duckdb", "*.ddb", "*.db"):

            duckdb_files.extend(glob.glob(os.path.join(self.db_directory, ext)))

            duckdb_files.extend(

                glob.glob(os.path.join(self.db_directory, "**", ext), recursive=True)

            )

        duckdb_files = list(set(duckdb_files))

        duckdb_files = [

            f for f in duckdb_files if os.path.isfile(f) and not is_sqlite_file(f)

        ]



        for db_file in duckdb_files:

            conn = None

            try:

                import duckdb

  # type: ignore

                conn = duckdb.connect(db_file, read_only=True)

                # Get tables  # type: ignore

                cursor = conn.execute("SHOW TABLES;")

                table_names = [r[0] for r in cursor.fetchall()]



                # -- Detect homogeneous table groups ------------------------------

                # When many tables share the same column schema (e.g., one table per

                # stock symbol or per entity), represent them as a single unified

                # virtual table so the LLM can reason about the combined data.

                HOMOGENEOUS_THRESHOLD = _load_homogeneous_threshold()  # configurable via system_params.yaml

                schema_groups: Dict[str, List[str]] = {}  # col_sig -> [table_names]

                table_col_info: Dict[str, List[Any]] = {}  # table_name -> col rows



                for t_name in table_names:

                    try:  # type: ignore

                        cols = conn.execute(

                            f"PRAGMA table_info('{t_name}');"

                        ).fetchall()

                        # Group by sorted lowercase column names to allow type coercion in UNION ALL

                        sig = "|".join(sorted(c[1].lower() for c in cols))

                        schema_groups.setdefault(sig, []).append(t_name)

                        table_col_info[t_name] = cols

                    except Exception:

                        pass



                # Build set of tables that are absorbed into a unified group

                absorbed_tables: set = set()

                for sig, group in schema_groups.items():

                    if len(group) < HOMOGENEOUS_THRESHOLD:

                        continue

                    # Create a unified SemanticTable for this group

                    rep_table = group[0]

                    cols = table_col_info.get(rep_table, [])

                    sample_data = []

                    try:  # type: ignore

                        cursor = conn.execute(f'SELECT * FROM "{rep_table}" LIMIT 3;')

                        desc = cursor.description

                        col_names_rep = [d[0] for d in desc] if desc else []

                        sample_data = [

                            dict(zip(col_names_rep, row, strict=False)) for row in cursor.fetchall()

                        ]

                    except Exception:

                        pass



                    db_basename = os.path.splitext(os.path.basename(db_file))[0]

                    unified_name = f"all_{db_basename}"



                    # Build unified columns: first add _entity_name, then the shared cols

                    unified_cols = [

                        SemanticColumn(

                            name="_entity_name",

                            type="VARCHAR",

                            description=(

                                f"The original table name (entity identifier, e.g., ticker symbol). "

                                f"This column is added by the executor when it creates the unified view. "

                                f"Sample values: {group[:10]}"

                            ),

                            sample_values=[str(g) for g in group[:10]],

                        )

                    ]

                    for col in cols:

                        col_name = col[1]

                        col_type = col[2]

                        raw_samples = [

                            row.get(col_name)

                            for row in sample_data

                            if row.get(col_name) is not None

                        ]

                        sample_vals = self._sanitize_sample_values(raw_samples)

                        hint = self._infer_column_hint(col_name, sample_vals)

                        unified_cols.append(

                            SemanticColumn(

                                name=col_name,

                                type=str(col_type),

                                description=f"Column '{col_name}' (shared across all entity tables){hint}",

                                sample_values=sample_vals,

                            )

                        )



                    preview = group[:5]

                    rest = len(group) - 5

                    preview_str = ", ".join(preview) + (

                        f" ' (+{rest} more)" if rest > 0 else ""

                    )

                    tables.append(

                        SemanticTable(

                            name=unified_name,

                            description=(

                                f"Unified view across {len(group)} homogeneous tables from '{os.path.basename(db_file)}'. "

                                f"Each original table represents one entity (e.g., a stock ticker). "

                                f"Tables: {preview_str}. "

                                f"The executor AUTO-CREATES this view at query time as a UNION ALL of all entity tables with '_entity_name' added. "

                                f"JOIN with other tables using: JOIN {unified_name} ON {unified_name}._entity_name = other_table.symbol_column"

                            ),

                            columns=unified_cols,

                            foreign_keys=[],

                            sample_rows=sample_data[:2],

                        )

                    )

                    for t in group:

                        absorbed_tables.add(t)

                    logger.info(

                        f"Unified {len(group)} homogeneous tables from '{db_basename}' => '{unified_name}'"

                    )



                # -- Process non-absorbed tables normally -------------------------

                for t_name in table_names:

                    if t_name in absorbed_tables:

                        continue  # type: ignore

                    cols = table_col_info.get(t_name)

                    if cols is None:

                        try:

                            cols = conn.execute(

                                f"PRAGMA table_info('{t_name}');"

                            ).fetchall()

                        except Exception as e:

                            logger.warning(

                                f"PRAGMA table_info failed for '{t_name}': {e}"

                            )

                            continue



                    columns = []

                    sample_data = []

                    try:  # type: ignore

                        cursor = conn.execute(f'SELECT * FROM "{t_name}" LIMIT 100;')

                        desc = cursor.description

                        col_names = [d[0] for d in desc] if desc else []

                        sample_data = [

                            dict(zip(col_names, row, strict=False)) for row in cursor.fetchall()

                        ]

                    except Exception:

                        sample_data = []



                    for col in cols:

                        col_name = col[1]

                        col_type = col[2]

                        raw_samples = [

                            row.get(col_name)

                            for row in sample_data

                            if row.get(col_name) is not None

                        ]

                        sample_vals = self._sanitize_sample_values(raw_samples)

                        hint = self._infer_column_hint(col_name, sample_vals)

                        columns.append(

                            SemanticColumn(

                                name=col_name,

                                type=str(col_type),

                                description=f"Column '{col_name}' in table '{t_name}'{hint}",

                                sample_values=sample_vals,

                            )

                        )



                    empty_note = (

                        " (WARNING: table has 0 rows -- data may require an external service)"

                        if not sample_data

                        else ""

                    )

                    tables.append(

                        SemanticTable(

                            name=t_name,

                            description=f"Table '{t_name}' loaded from DuckDB database{empty_note}",

                            columns=columns,

                            foreign_keys=[],

                            sample_rows=sample_data[:2],

                        )

                    )

            except Exception as e:

                logger.warning(

                    f"Failed to dynamically extract DuckDB schema from {db_file}: {e}"

                )

            finally:

                if conn:

                    with contextlib.suppress(Exception):

                        conn.close()



        # 3. Look for Postgres database if the db_name matches a Postgres DB

        # Only query if we have no tables yet and a postgres client is running or configured in sf_credentials

        if not tables:

            try:

                # Check config

                from agent.app.core.config import CONFIG_DIR



                credentials_path = CONFIG_DIR / "sf_credentials.json"

                if credentials_path.exists():

                    with open(credentials_path, "r", encoding="utf-8") as f:

                        creds = json.load(f)

                    pg_cfg = creds.get("postgres", {})

                    if pg_cfg and self.db_name:

                        import psycopg2

                        import psycopg2.extras



                        host = pg_cfg.get("host", "localhost")

                        port = pg_cfg.get("port", 5432)

                        user = pg_cfg.get("user", "postgres")

                        password = pg_cfg.get("password", "postgres")

                        dbname = pg_cfg.get("dbname", self.db_name.lower())



                        conn = psycopg2.connect(

                            f"host={host} port={port} user={user} password={password} dbname={dbname}"

                        )

                        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                        # Get user tables

                        cur.execute(

                            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"

                        )

                        table_names = [r["table_name"] for r in cur.fetchall()]



                        for t_name in table_names:

                            # Get columns

                            cur.execute(

                                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s;",

                                (t_name,),

                            )

                            cols = cur.fetchall()



                            columns = []

                            # Get sample rows

                            try:

                                cur.execute(f'SELECT * FROM "{t_name}" LIMIT 100;')

                                sample_data = [dict(r) for r in cur.fetchall()]

                            except Exception:

                                sample_data = []



                            for col in cols:

                                col_name = col["column_name"]

                                col_type = col["data_type"]



                                raw_samples = []

                                for row in sample_data:

                                    val = row.get(col_name)

                                    if val is not None:

                                        raw_samples.append(val)



                                columns.append(

                                    SemanticColumn(

                                        name=col_name,

                                        type=col_type,

                                        description=f"Column '{col_name}' in table '{t_name}'",

                                        sample_values=self._sanitize_sample_values(

                                            raw_samples

                                        ),

                                    )

                                )



                            prefix = (

                                f"{self.db_name}.{self.schema_name}."

                                if self.db_name and self.schema_name

                                else ""

                            )

                            fqn = f"{prefix}{t_name}" if prefix else t_name



                            tables.append(

                                SemanticTable(

                                    name=fqn,

                                    description=f"Table '{t_name}' loaded from PostgreSQL database",

                                    columns=columns,

                                    foreign_keys=[],

                                    sample_rows=sample_data[:2],

                                )

                            )

                        cur.close()

                        conn.close()

            except Exception as e:

                logger.warning(f"Failed to dynamically extract PostgreSQL schema: {e}")



        # 4. Look for MongoDB database if configured

        if not tables:

            try:

                mongo_uri = os.getenv("MONGO_URI")

                if mongo_uri and self.db_name:

                    import pymongo

  # type: ignore

                    client = pymongo.MongoClient(

                        mongo_uri, serverSelectionTimeoutMS=2000

                    )

                    dbname = self.db_name.lower()

                    db = client[dbname]

                    # Check collections

                    collections = db.list_collection_names()

                    for t_name in collections:

                        if t_name.startswith("system."):

                            continue

                        # Sample docs to extract schema

                        sample_data = list(db[t_name].find().limit(100))



                        # Find all keys  # type: ignore

                        keys_schema = {}

                        for doc in sample_data:

                            for k, v in doc.items():

                                if k == "_id":

                                    continue

                                v_type = type(v).__name__

                                keys_schema.setdefault(k, set()).add(v_type)



                        columns = []

                        for col_name, types_set in keys_schema.items():

                            col_type = "/".join(types_set)



                            raw_samples = []

                            for doc in sample_data:

                                val = doc.get(col_name)

                                if val is not None:

                                    raw_samples.append(val)



                            columns.append(

                                SemanticColumn(

                                    name=col_name,

                                    type=col_type,

                                    description=f"Key '{col_name}' in MongoDB collection '{t_name}'",

                                    sample_values=self._sanitize_sample_values(

                                        raw_samples

                                    ),

                                )

                            )



                        # Convert ObjectId to str for sample rows JSON compatibility

                        serializable_samples = []

                        for doc in sample_data[:2]:

                            serializable_doc = {}

                            for k, v in doc.items():

                                if k == "_id":

                                    serializable_doc[k] = str(v)

                                else:

                                    serializable_doc[k] = v

                            serializable_samples.append(serializable_doc)



                        prefix = (

                            f"{self.db_name}.{self.schema_name}."

                            if self.db_name and self.schema_name

                            else ""

                        )

                        fqn = f"{prefix}{t_name}" if prefix else t_name



                        tables.append(

                            SemanticTable(

                                name=fqn,

                                description=f"Collection '{t_name}' loaded from MongoDB database",

                                columns=columns,

                                foreign_keys=[],

                                sample_rows=serializable_samples,

                            )

                        )

                    client.close()

            except Exception as e:

                logger.warning(f"Failed to dynamically extract MongoDB schema: {e}")



        return tables

