import os
import json
from typing import List, Dict
from src.schema.models import SemanticContext, SemanticTable, SemanticColumn
from src.utils.logger import logger

class SemanticContextEngine:
    def __init__(self, db_directory: str, max_sample_values: int = 15):
        self.db_directory = os.path.normpath(db_directory)
        self.max_sample_values = max_sample_values
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
        logger.info(f"Building Governed Semantic Context from: {self.db_directory}")
        tables: List[SemanticTable] = []
        
        if not os.path.exists(self.db_directory):
            logger.error(f"Directory not found: {self.db_directory}")
            return SemanticContext(tables=[])

        for filename in os.listdir(self.db_directory):
            if not filename.endswith(".json"):
                continue
                
            filepath = os.path.join(self.db_directory, filename)
            table_name = filename.replace(".json", "")
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                columns: List[SemanticColumn] = []

                # ── Format A: IDC-style ──────────────────────────────────
                if "columns" in data and isinstance(data["columns"], list) and \
                        data["columns"] and isinstance(data["columns"][0], dict):
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
                            sample_values=unique_samples
                        ))

                foreign_keys = data.get("foreign_keys", [])
                fk_strings = [str(fk) for fk in foreign_keys] if isinstance(foreign_keys, list) else []

                # Prefer table_fullname if available (Format B provides it authoratively)
                fqn = data.get("table_fullname") or (
                    f"{self.fqn_prefix}{table_name}" if self.fqn_prefix else table_name
                )
                table = SemanticTable(
                    name=fqn,
                    description=data.get("description", f"Table containing {table_name} data")
                              if isinstance(data.get("description"), str) else f"Table containing {table_name} data",
                    columns=columns,
                    foreign_keys=fk_strings
                )
                tables.append(table)
                logger.debug(f"Parsed [{fqn}] — {len(columns)} columns")
                
            except Exception as e:
                logger.warning(f"Failed to parse {filename}: {str(e)}")

        self.context = SemanticContext(tables=tables)
        logger.success(f"Built Semantic Context with {len(tables)} tables.")
        return self.context

    def format_for_prompt(self, relevant_tables: List[str] = None, table_columns: Dict[str, List[str]] = None, slim: bool = False, include_samples: bool = False) -> str:
        """Returns a highly compressed YAML-like string representation of the Semantic Context.
        If slim=True, only table names and descriptions are included (used for table pruning).
        If include_samples=True, sample values are included (used for final schema linking).
        """
        if not self.context:
            self.build_context()
            
        lines = ["# GOVERNED SEMANTIC CONTEXT\n"]
        if self.fqn_prefix:
            lines.append(f"# NOTE: All table names are FULLY QUALIFIED as {self.fqn_prefix}<TABLE>. Use them exactly as shown.\n")
        
        for table in self.context.tables:
            # Table-level filtering
            if relevant_tables and table.name not in relevant_tables:
                if not any(t in table.name for t in relevant_tables):
                    continue

            lines.append(f"Table: {table.name}")
            if table.description:
                lines.append(f"  Description: {table.description}")
            
            if slim:
                continue

            if table.foreign_keys:
                lines.append(f"  Foreign Keys: {', '.join(table.foreign_keys)}")
            lines.append("  Columns:")
            
            target_cols = table_columns.get(table.name) if table_columns else None
            
            for col in table.columns:
                if target_cols and col.name not in target_cols:
                    continue

                desc = f" - {col.description}" if col.description else ""
                lines.append(f"    - {col.name} ({col.type}){desc}")
                if include_samples and col.sample_values:
                    lines.append(f"      Sample Values: {', '.join(col.sample_values)}")
            lines.append("") # Empty line between tables
            
        return "\n".join(lines)
