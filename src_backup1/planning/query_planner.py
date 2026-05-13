from typing import List, Set, Dict, Any
from src.core.models import Intent, ColumnMapping, SQLPlan, Filter
from src.planning.schema_graph import SchemaGraph
from src.utils.logger import logger

class QueryPlanner:
    def __init__(self, graph: SchemaGraph):
        self.graph = graph

    def plan(self, intent: Intent, mappings: List[ColumnMapping]) -> SQLPlan:
        if not mappings:
            return SQLPlan(base_table="unknown", limit=intent.limit)

        # 1. Select Base Table
        table_counts = {}
        for m in mappings:
            t = m.column.table
            table_counts[t] = table_counts.get(t, 0) + 1
        base_table = max(table_counts, key=table_counts.get)
        
        # 2. Required Tables & Joins
        required_tables = {m.column.table for m in mappings}
        other_tables = required_tables - {base_table}
        joins = self.graph.find_path(base_table, other_tables)
        
        # 3. Filters & Projections
        filters = []
        projections = []
        
        # Process Mappings
        for m in mappings:
            col_ref = self._get_col_ref(m)
            
            if m.source_type == "filter":
                # Find the filter object in intent
                filt = next((f for f in intent.flatten_filters() if f.field == m.source_name or str(f.value) == m.source_name), None)
                if filt:
                    val = filt.value
                    op = filt.operator
                    
                    # Value Grounding
                    if isinstance(val, str) and m.column.sample_values:
                        val_lower = val.lower()
                        for s in m.column.sample_values:
                            if str(s).lower() == val_lower or str(s).lower().replace('-', '_') == val_lower.replace('-', '_'):
                                val = str(s)
                                break
                    
                    if isinstance(val, list):
                        items = [f"'{v}'" if isinstance(v, str) else str(v) for v in val]
                        filters.append(f"{col_ref} IN ({', '.join(items)})")
                    else:
                        formatted_val = f"'{val}'" if isinstance(val, str) else str(val)
                        filters.append(f"{col_ref} {op} {formatted_val}")
            
            elif m.source_type == "entity":
                projections.append(col_ref)

        # 4. Defaults
        projections = list(dict.fromkeys(projections))
        if not projections:
            # Project all mapped columns if no specific entities
            projections = [self._get_col_ref(m) for m in mappings]
            
        if not projections:
            projections = ["*"]

        return SQLPlan(
            base_table=base_table,
            joins=joins,
            filters=filters,
            projections=projections,
            limit=intent.limit,
            order_by=intent.order_by
        )

    def _get_col_ref(self, m: ColumnMapping) -> str:
        col = m.column
        # Handle multiple json_paths (just pick first for now or use JSON_EXTRACT logic)
        if col.json_paths:
            path = col.json_paths[0]
            return f"{col.table}.{col.column}:{path}"
        return f"{col.table}.{col.column}"
