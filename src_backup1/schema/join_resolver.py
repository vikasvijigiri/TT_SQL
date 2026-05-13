from dataclasses import dataclass
from typing import List, Dict, Tuple, Set, Optional, Any
from src.utils.logger import logger
from src.schema.schema_graph_builder import JoinStep

@dataclass
class JoinPlan:
    requires_join: bool
    primary_table: str
    steps: List[JoinStep]
    unresolvable_pairs: List[Tuple[str, str]]
    requires_human_review: bool = False

class JoinResolver:
    """
    Resolves multi-table join paths automatically using the schema graph.
    """
    
    def __init__(self, schema_graph_builder):
        self.builder = schema_graph_builder
        self.graph = schema_graph_builder.graph

    def infer_joins(self, resolved_conditions: List[Dict[str, Any]], primary_table: Optional[str] = None) -> JoinPlan:
        """
        Infers the shortest join path to connect all tables referenced in the conditions.
        """
        # 1. Identify all unique tables
        referenced_tables = set()
        for cond in resolved_conditions:
            table = cond.get("resolved_table")
            if table:
                referenced_tables.add(table)
        
        if not referenced_tables:
            return JoinPlan(requires_join=False, primary_table="", steps=[], unresolvable_pairs=[])

        # 2. Determine primary table if not provided
        if not primary_table:
            # Pick the table with most conditions or just the first one
            table_counts = {}
            for cond in resolved_conditions:
                t = cond.get("resolved_table")
                if t: table_counts[t] = table_counts.get(t, 0) + 1
            primary_table = max(table_counts, key=table_counts.get) if table_counts else list(referenced_tables)[0]

        if len(referenced_tables) == 1 and list(referenced_tables)[0] == primary_table:
            return JoinPlan(requires_join=False, primary_table=primary_table, steps=[], unresolvable_pairs=[])

        # 3. Resolve paths from primary table to all others
        steps = []
        unresolvable = []
        visited_tables = {primary_table}
        tables_to_connect = referenced_tables - {primary_table}
        
        for target_table in tables_to_connect:
            path = self.builder.resolve_join_path(primary_table, target_table)
            if path:
                steps.extend(path)
            else:
                unresolvable.append((primary_table, target_table))
                
        return JoinPlan(
            requires_join=len(steps) > 0,
            primary_table=primary_table,
            steps=steps,
            unresolvable_pairs=unresolvable,
            requires_human_review=len(unresolvable) > 0
        )

    def to_sql_fragment(self, join_plan: JoinPlan) -> str:
        """
        Returns the JOIN ... ON ... clauses as a SQL string fragment.
        """
        if not join_plan.requires_join:
            return ""
            
        sql_parts = []
        for step in join_plan.steps:
            # Render each step
            sql_parts.append(
                f"{step.join_type} JOIN {step.right_table} ON {step.left_table}.{step.left_col} = {step.right_table}.{step.right_col}"
            )
            
        return "\n".join(sql_parts)
