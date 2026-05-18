import re
import logging
from typing import List, Dict, Any
from backend.app.repositories.db_executor import DatabaseExecutor
from backend.app.utils.logger import logger

class DynamicProfiler:
    """
    Reflective Schema Profiler Agent.
    Runs fast metadata profiling queries on ambiguous or rich column types
    (Variant, Geography, JSON, WKT, value coordinates) to discover structural formats dynamically.
    """
    
    def __init__(self):
        self.ambiguity_keywords = [
            "largest", "smallest", "max", "min", "longest", "shortest", 
            "distance", "area", "json", "xml", "nested", "value", 
            "coordinate", "shape", "geom", "characteristics", "relationship"
        ]

    def _should_profile(self, user_query: str, column_fqn: str) -> bool:
        """Heuristically decides if a column warrants active profiling."""
        query_lower = user_query.lower()
        col_lower = column_fqn.lower()
        
        # 1. Check if query asks for size, aggregation, spatial, or variant features
        has_query_trigger = any(kw in query_lower for kw in self.ambiguity_keywords)
        
        # 2. Check if the column name itself suggests it contains generic, rich, or spatial data
        has_col_trigger = any(kw in col_lower for kw in ["value", "coord", "geom", "shape", "type", "char", "rel"])
        
        return has_query_trigger or has_col_trigger

    def profile_columns(self, user_query: str, selected_columns: List[str], executor: DatabaseExecutor) -> str:
        """
        Runs non-disruptive, ultra-fast profiling queries on qualified columns.
        Returns a formatted markdown knowledge snippet.
        """
        logger.set_agent("PROFILER")
        logger.info("Evaluating selected columns for active schema profiling...")
        
        profiling_insights = []
        profiled_count = 0
        
        for col_fqn in selected_columns:
            if not self._should_profile(user_query, col_fqn):
                continue
                
            # Restrict to at most 3 profiling targets to avoid excessive overhead
            if profiled_count >= 3:
                break
                
            parts = col_fqn.split(".")
            if len(parts) < 2:
                continue
                
            # Strip outer double quotes and backslashes from each part before single double-quoting
            clean_parts = [p.replace('"', '').replace('\\', '').strip() for p in parts]
            col_name = clean_parts[-1]
            
            quoted_col = f'"{col_name}"'
            quoted_table = ".".join(f'"{p}"' for p in clean_parts[:-1])
            
            logger.info(f"Running active profiling probe on: {quoted_table}.{quoted_col}")
            
            # Probe 1: Frequency and distinct distribution check (Universal SQL)
            type_probe_sql = f'SELECT {quoted_col} AS val, COUNT(*) AS cnt FROM {quoted_table} WHERE {quoted_col} IS NOT NULL GROUP BY {quoted_col} ORDER BY cnt DESC LIMIT 3'
            
            # Probe 2: Fetch raw sample values to expose coordinate structure, formats, JSON keys
            sample_probe_sql = f'SELECT {quoted_col} FROM {quoted_table} WHERE {quoted_col} IS NOT NULL LIMIT 3'
            
            try:
                # Run Probe 1 (Frequency)
                success1, msg1, rows1 = executor.execute_direct(type_probe_sql)
                # Run Probe 2 (Samples)
                success2, msg2, rows2 = executor.execute_direct(sample_probe_sql)
                
                insight = f"### Live Profiling Insights for `{col_fqn}`:\n"
                
                if success1 and rows1:
                    insight += "- **Top Frequent Values & Distribution:**\n"
                    for r in rows1:
                        insight += f"  * Value: `{r.get('VAL', 'UNKNOWN')}` | Frequency Count: {r.get('CNT', 0)}\n"
                        
                if success2 and rows2:
                    insight += "- **Empirical Sample Formats:**\n"
                    for i, r in enumerate(rows2):
                        val_str = str(r.get(col_name.upper(), r.get(col_name, '')))
                        # Truncate extremely long values (like huge GeoJSONs) to prevent token bloat
                        if len(val_str) > 400:
                            val_str = val_str[:400] + "... [TRUNCATED]"
                        insight += f"  * Sample {i+1}: `{val_str}`\n"

                
                if (success1 and rows1) or (success2 and rows2):
                    profiling_insights.append(insight)
                    profiled_count += 1
                    
            except Exception as e:
                # Completely safe: log failure and continue so the pipeline is never disrupted
                logger.warning(f"Profiling failed for column {col_fqn}: {e}")
                
        logger.reset_agent()
        
        if profiling_insights:
            return "\n\n".join(profiling_insights)
        return ""
