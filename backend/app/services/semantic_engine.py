import os
import json
import pandas as pd
from typing import List, Dict
from backend.app.models.schemas import SemanticContext, SemanticTable, SemanticColumn
from backend.app.utils.logger import logger

class SemanticContextEngine:
    def __init__(self, db_directory: str, max_sample_values: int = 15, silent: bool = False):
        self.db_directory = os.path.normpath(db_directory)
        self.max_sample_values = max_sample_values
        self.silent = silent
        self.context: SemanticContext = None
        # Derive DB.SCHEMA prefix from directory path:
        # Expected layout: resources/databases/{dialect}/{DB}/{SCHEMA}/
        parts = self.db_directory.replace("\\", "/").split("/")
        # Walk back to find the two segments after the dialect folder
        try:
            dialect_idx = next(i for i, p in enumerate(parts) if p in ("snowflake", "bigquery", "sqlite"))
            self.db_name = parts[dialect_idx + 1] if dialect_idx + 1 < len(parts) else ""
            self.schema_name = parts[dialect_idx + 2] if dialect_idx + 2 < len(parts) else ""
        except StopIteration:
            self.db_name = ""
            self.schema_name = ""
        self.fqn_prefix = f"{self.db_name}.{self.schema_name}." if self.db_name and self.schema_name else ""

    def build_context(self) -> SemanticContext:
        """Parses local JSON metadata files to build the Governed Semantic Context.
        Supports two JSON formats:
          Format A (IDC-style):   {columns: [{column_name, type, sample_values}], foreign_keys}
          Format B (Spider-style): {table_fullname, column_names, column_types, description, sample_rows}
        """
        if not self.silent:
            logger.info(f"Building Governed Semantic Context from: {self.db_directory}")
        tables: List[SemanticTable] = []
        
        if not os.path.exists(self.db_directory):
            logger.error(f"Directory not found: {self.db_directory}")
            return SemanticContext(tables=[])

        for root, dirs, files in os.walk(self.db_directory):
            for filename in files:
                if not filename.endswith(".json"):
                    continue
                    
                filepath = os.path.join(root, filename)
                table_name = filename.replace(".json", "")
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    columns: List[SemanticColumn] = []
                    sample_rows: List[dict] = []

                    # ── Format A: IDC-style ──────────────────────────────────
                    if "columns" in data and isinstance(data["columns"], list) and \
                            data["columns"] and isinstance(data["columns"][0], dict):
                        samples = data.get("sample", []) or data.get("all_samples", []) or data.get("sample_rows", [])
                        if isinstance(samples, list):
                            sample_rows = [s for s in samples if isinstance(s, dict)]
                        for col_data in data["columns"]:
                            raw_samples = col_data.get("sample_values", [])
                            str_samples = [str(v) for v in raw_samples if v is not None]
                            unique_samples = list(dict.fromkeys(str_samples))[:self.max_sample_values]
                            columns.append(SemanticColumn(
                                name=col_data.get("column_name", ""),
                                type=col_data.get("type", "UNKNOWN"),
                                description=col_data.get("description", ""),
                                sample_values=unique_samples
                            ))

                    # ── Format B: Spider2-style ──────────────────────────────
                    elif "column_names" in data:
                        col_names = data.get("column_names", [])
                        col_types = data.get("column_types", [])
                        col_descs = data.get("description", [])
                        sample_rows = data.get("sample_rows", [])
                        
                        # Discover nested keys for VARIANT/JSON columns
                        nested_map = {}
                        for row in sample_rows:
                            for col_name, val in row.items():
                                if isinstance(val, str) and (val.startswith('{') or val.startswith('[')):
                                    try:
                                        parsed = json.loads(val)
                                        keys = []
                                        if isinstance(parsed, dict): keys = list(parsed.keys())
                                        elif isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                                            keys = list(parsed[0].keys())
                                        if keys:
                                            if col_name not in nested_map: nested_map[col_name] = set()
                                            nested_map[col_name].update(keys)
                                    except: pass

                        # Build per-column sample values from sample_rows
                        col_samples: dict = {n: [] for n in col_names}
                        for row in sample_rows:
                            for n in col_names:
                                val = row.get(n)
                                if val is not None and str(val) not in col_samples[n]:
                                    col_samples[n].append(str(val))

                        for idx, col_name in enumerate(col_names):
                            col_type = col_types[idx] if idx < len(col_types) else "UNKNOWN"
                            col_desc = col_descs[idx] if idx < len(col_descs) else ""
                            unique_samples = col_samples[col_name][:self.max_sample_values]
                            columns.append(SemanticColumn(
                                name=col_name,
                                type=col_type,
                                description=col_desc,
                                sample_values=unique_samples,
                                nested_keys=list(nested_map.get(col_name, []))
                            ))

                    foreign_keys = data.get("foreign_keys", [])
                    fk_strings = [str(fk) for fk in foreign_keys] if isinstance(foreign_keys, list) else []

                    schema_part = self.schema_name
                    if not schema_part:
                        rel_dir = os.path.relpath(root, self.db_directory).replace("\\", "/")
                        if rel_dir != "." and "/" not in rel_dir:
                            schema_part = rel_dir
                    prefix = f"{self.db_name}.{schema_part}." if self.db_name and schema_part else self.fqn_prefix

                    fqn = data.get("table_fullname") or (f"{prefix}{table_name}" if prefix else table_name)
                    table = SemanticTable(
                        name=fqn,
                        description=data.get("description", f"Table containing {table_name} data")
                                  if isinstance(data.get("description"), str) else f"Table containing {table_name} data",
                        columns=columns,
                        foreign_keys=fk_strings,
                        sample_rows=sample_rows[:2] # Store a couple of rows for evidence
                    )
                    tables.append(table)
                    logger.debug(f"Parsed [{fqn}] — {len(columns)} columns")
                    
                except Exception as e:
                    logger.warning(f"Failed to parse {filename}: {str(e)}")

        self.context = SemanticContext(tables=tables)
        if not self.silent:
            logger.success(f"Built Semantic Context with {len(tables)} tables.")
        return self.context

    def format_for_prompt(self, relevant_tables: List[str] = None, table_columns: Dict[str, List[str]] = None, slim: bool = False, include_samples: bool = False) -> str:
        """Returns a highly compressed YAML-like string representation of the Semantic Context.
        Uses Enterprise SchemaCompressor to eliminate raw row dumps and massive JSON samples.
        """
        if not self.context:
            self.build_context()
            
        from backend.app.core.schema.schema_compressor import SchemaCompressor
        from backend.app.core.pipeline_config import BALANCED_CONFIG

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
            table_columns=table_columns
        )
        
        logger.debug(f"[SemanticEngine] Formatted prompt schema (~{len(compressed_schema)//4} tokens).")
        return compressed_schema


    def discover_and_load_table(self, table_name: str) -> List[SemanticTable]:
        """Scans neighboring database directories under resources/databases/{dialect} 
        for a table matching table_name (case-insensitively). Loads and registers it 
        in the context.
        """
        # Determine dialect from current db_directory
        parts = self.db_directory.replace("\\", "/").split("/")
        dialect = "snowflake"
        try:
            dialect_idx = next(i for i, p in enumerate(parts) if p in ("snowflake", "bigquery", "sqlite"))
            dialect = parts[dialect_idx]
        except StopIteration:
            pass

        # Use resources/databases/{dialect} as search root
        base_dir = os.path.dirname(self.db_directory)
        if not os.path.exists(base_dir):
            return []

        search_term = table_name.lower().replace('"', '').replace('`', '').strip()
        # Handle cases where table name has schema prefix or FQN, grab the base name
        if "." in search_term:
            search_term = search_term.split(".")[-1]

        # Ignore very generic or short words
        if len(search_term) < 3:
            return []

        import glob
        pattern = os.path.join(base_dir, "**", "*.json")
        matching_files = []
        for filepath in glob.glob(pattern, recursive=True):
            filename = os.path.basename(filepath)
            t_name = filename.replace(".json", "").lower()
            # If search term is a substring or vice versa
            if search_term in t_name or t_name in search_term:
                matching_files.append(filepath)

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
            if self.context and any(t.name.upper() == fqn.upper() for t in self.context.tables):
                continue

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                columns: List[SemanticColumn] = []
                sample_rows = data.get("sample_rows", []) or data.get("sample", []) or []

                # Format A / B parser logic
                if "columns" in data and isinstance(data["columns"], list):
                    for col_data in data["columns"]:
                        raw_samples = col_data.get("sample_values", [])
                        str_samples = [str(v) for v in raw_samples if v is not None]
                        columns.append(SemanticColumn(
                            name=col_data.get("column_name", ""),
                            type=col_data.get("type", "UNKNOWN"),
                            description=col_data.get("description", ""),
                            sample_values=list(dict.fromkeys(str_samples))[:self.max_sample_values]
                        ))
                elif "column_names" in data:
                    col_names = data.get("column_names", [])
                    col_types = data.get("column_types", [])
                    col_descs = data.get("description", [])
                    col_samples = {n: [] for n in col_names}
                    for row in sample_rows:
                        if isinstance(row, dict):
                            for n in col_names:
                                val = row.get(n)
                                if val is not None and str(val) not in col_samples[n]:
                                    col_samples[n].append(str(val))

                    for idx, col_name in enumerate(col_names):
                        col_type = col_types[idx] if idx < len(col_types) else "UNKNOWN"
                        col_desc = col_descs[idx] if idx < len(col_descs) else ""
                        columns.append(SemanticColumn(
                            name=col_name,
                            type=col_type,
                            description=col_desc,
                            sample_values=col_samples[col_name][:self.max_sample_values]
                        ))

                table_obj = SemanticTable(
                    name=fqn,
                    description=data.get("description", f"Table containing {tbl} data")
                               if isinstance(data.get("description"), str) else f"Table containing {tbl} data",
                    columns=columns,
                    foreign_keys=[str(fk) for fk in data.get("foreign_keys", [])],
                    sample_rows=sample_rows[:2]
                )
                if not self.context:
                    self.context = SemanticContext(tables=[])
                self.context.tables.insert(0, table_obj)
                loaded_tables.append(table_obj)
                logger.info(f"Dynamically discovered and loaded cross-database table: {fqn}")
            except Exception as e:
                logger.warning(f"Failed to dynamically load {filepath}: {e}")

        return loaded_tables

