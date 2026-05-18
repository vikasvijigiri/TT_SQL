import json
from typing import List, Dict, Any, Optional
from backend.app.models.schemas import SemanticContext, SemanticTable, SemanticColumn
from backend.app.core.pipeline_config import PipelineModeConfig, BALANCED_CONFIG

class SchemaCompressor:
    """
    Enterprise schema compression engine. Replaces raw row dumps and massive JSON
    samples with concise typed object signatures and statistical metadata.
    """
    def __init__(self, config: PipelineModeConfig = BALANCED_CONFIG):
        self.config = config
        self.level = config.schema_compression_level

    def compress_variant_column(self, col: SemanticColumn) -> str:
        """
        Transforms raw variant/json columns or nested keys into a concise typed object signature.
        Example: VARIANT<OBJECT{genotype: ARRAY<INTEGER>, call_set_name: STRING, DS: FLOAT}>
        """
        if not col.nested_keys:
            return "VARIANT<JSON>"

        formatted_keys = []
        for key in col.nested_keys[:15]: # cap at top 15 nested keys
            key_clean = key.strip().replace('"', '').replace("'", "")
            k_lower = key_clean.lower()
            # Infer basic type if naming hint exists (check arrays & numbers first)
            if any(h in k_lower for h in ("arr", "list", "genotype", "items", "calls")):
                k_type = "ARRAY"
            elif any(h in k_lower for h in ("count", "num", "idx", "len", "seq")):
                k_type = "INTEGER"
            elif any(h in k_lower for h in ("val", "score", "rate", "pct", "avg", "std", "ds")):
                k_type = "FLOAT"
            elif any(h in k_lower for h in ("date", "time", "created", "updated")):
                k_type = "TIMESTAMP"
            elif any(h in k_lower for h in ("id", "name", "code", "str", "desc", "type")):
                k_type = "STRING"
            else:
                k_type = "VARIANT"
            formatted_keys.append(f"{key_clean}: {k_type}")

        sig = ", ".join(formatted_keys)
        return f"VARIANT<OBJECT{{{sig}}}>"

    def compress_column(self, col: SemanticColumn, is_sf: bool = True) -> str:
        col_name = f'"{col.name}"' if (is_sf and not col.name.startswith('"')) else col.name
        col_type = col.type.upper()
        
        if "VARIANT" in col_type or "JSON" in col_type or bool(col.nested_keys):
            col_type_str = self.compress_variant_column(col)
        else:
            col_type_str = col_type

        parts = [f"- {col_name} ({col_type_str})"]
        
        if self.level != "aggressive" and col.description:
            desc_clean = col.description.strip().replace("\n", " ")
            if len(desc_clean) > 85:
                desc_clean = desc_clean[:82] + "..."
            parts.append(f"  Desc: {desc_clean}")

        if self.level == "verbose":
            max_s = self.config.max_sample_values_per_col
        elif self.level == "balanced":
            max_s = min(3, self.config.max_sample_values_per_col)
        else:
            max_s = 0

        if max_s > 0 and col.sample_values:
            clean_samples = []
            for s in col.sample_values:
                s_str = str(s).strip()
                # filter out giant json blocks or huge text
                if len(s_str) < 60 and not (s_str.startswith("{") and s_str.endswith("}")):
                    clean_samples.append(s_str)
            if clean_samples:
                limited = ", ".join(clean_samples[:max_s])
                parts.append(f"  Samples: [{limited}]")
                
        return "\n".join(parts)

    def compress_table(self, table: SemanticTable, is_sf: bool = True, target_cols: List[str] = None) -> str:
        tbl_name = f'"{table.name}"' if (is_sf and not table.name.startswith('"')) else table.name
        lines = [f"Table: {tbl_name}"]
        
        if self.level != "aggressive" and table.description:
            lines.append(f"  Description: {table.description.strip()}")
            
        if table.foreign_keys:
            lines.append(f"  Foreign Keys: {', '.join(table.foreign_keys)}")

        lines.append("  Columns:")
        for col in table.columns:
            if target_cols and col.name not in target_cols:
                continue
            col_compressed = self.compress_column(col, is_sf=is_sf)
            for part in col_compressed.split("\n"):
                lines.append(f"    {part}")

        if self.level == "verbose" and self.config.include_raw_sample_rows and table.sample_rows:
            lines.append("  Table Sample (1 Row):")
            try:
                row = table.sample_rows[0]
                compact_row = {k: (str(v)[:100] + "..." if isinstance(v, str) and len(str(v)) > 100 else v) for k, v in row.items()}
                lines.append(f"    {json.dumps(compact_row)}")
            except: pass

        return "\n".join(lines)

    def compress_database_schema(self, context: SemanticContext, is_sf: bool = True, relevant_tables: List[str] = None, table_columns: Dict[str, List[str]] = None) -> str:
        if not context or not context.tables:
            return "# Empty Schema Context"
            
        lines = ["# COMPRESSED SEMANTIC DATABASE SCHEMA\n"]
        for table in context.tables:
            if relevant_tables is not None:
                tbl_clean = table.name.lower().replace('"', '')
                match = False
                for rt in relevant_tables:
                    rt_clean = rt.lower().replace('"', '')
                    if tbl_clean == rt_clean or tbl_clean.endswith("." + rt_clean.split('.')[-1]):
                        match = True
                        break
                if not match:
                    continue
            
            t_cols = table_columns.get(table.name) if table_columns else None
            tbl_compressed = self.compress_table(table, is_sf=is_sf, target_cols=t_cols)
            lines.append(tbl_compressed)
            lines.append("")
            
        return "\n".join(lines).strip()
