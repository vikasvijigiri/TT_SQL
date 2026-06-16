from core.logger import Logger
from core.schema_graph import SchemaGraph, JoinRanker

class QueryPlanner:
    """
    Builds an execution plan based on mappings and schema graph.
    """

    def __init__(self, schema_graph: SchemaGraph, join_ranker: JoinRanker):
        self.schema_graph = schema_graph
        self.join_ranker = join_ranker

    def build(self, mappings: list[dict]) -> dict:
        """
        Builds a query plan (Step 8):
        - determine base table
        - find join path using schema graph
        - apply ranked joins
        """
        if not mappings:
            return {"error": "No mappings provided"}

        # Determine all required tables
        required_tables = list(set([m["mapping"]["table"] for m in mappings]))
        
        # Determine base table (table with most mappings)
        table_counts = {}
        for m in mappings:
            t = m["mapping"]["table"]
            table_counts[t] = table_counts.get(t, 0) + 1
        
        base_table = max(table_counts, key=table_counts.get)
        
        # Find paths to all other required tables
        full_join_path = []
        visited_tables = {base_table}
        
        for target in required_tables:
            if target in visited_tables:
                continue
            
            # Find path from any visited table to the target
            best_sub_path = None
            min_len = 999
            
            for start_node in visited_tables:
                paths = self.schema_graph.find_all_paths(start_node, target)
                if paths:
                    ranked = self.join_ranker.rank_join_paths(paths)
                    if len(ranked[0]) < min_len:
                        min_len = len(ranked[0])
                        best_sub_path = (start_node, ranked[0])
            
            if best_sub_path:
                start_node, sub_path = best_sub_path
                current_source = start_node
                for edge in sub_path:
                    full_join_path.append({
                        "source_table": current_source,
                        "target_table": edge["to"],
                        "source_col": edge["source_col"],
                        "target_col": edge["target_col"]
                    })
                    current_source = edge["to"]
                    visited_tables.add(current_source)
            else:
                Logger.log(f"No join path found to {target}", level="WARN")

        return {
            "base_table": base_table,
            "joins": full_join_path,
            "mappings": mappings
        }
