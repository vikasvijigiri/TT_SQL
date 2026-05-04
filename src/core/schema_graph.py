import collections

class SchemaGraph:
    """
    Represents the database schema as a graph where tables are nodes and join relationships are edges.
    Edges store the specific columns used for joins.
    """

    def __init__(self, schema_info: dict):
        self.graph = collections.defaultdict(list)
        self.build_graph(schema_info)

    def build_graph(self, schema_info: dict):
        """
        Builds the graph from schema_info foreign keys.
        Each edge is: (neighbor_table, source_col, target_col)
        """
        for table, data in schema_info.items():
            fks = data.get("foreign_keys", [])
            for fk in fks:
                ref_table = fk.get("ref_table")
                source_col = fk.get("column")
                target_col = fk.get("ref_column")
                
                if ref_table and source_col and target_col:
                    # Add directed edge
                    self.graph[table].append({
                        "to": ref_table,
                        "source_col": source_col,
                        "target_col": target_col
                    })
                    # Add reverse edge for undirected traversal
                    self.graph[ref_table].append({
                        "to": table,
                        "source_col": target_col,
                        "target_col": source_col
                    })

    def find_all_paths(self, start_table: str, end_table: str, max_depth: int = 5) -> list[list[dict]]:
        """
        Finds all paths between two tables. 
        Each step in a path is a dict with 'to', 'source_col', 'target_col'.
        """
        paths = []
        # Queue stores (current_table, path_so_far)
        queue = collections.deque([(start_table, [])])
        
        while queue:
            node, path = queue.popleft()
            
            if node == end_table:
                paths.append(path)
                continue
                
            if len(path) >= max_depth:
                continue
                
            for edge in self.graph.get(node, []):
                neighbor = edge["to"]
                # Avoid cycles in table names
                if neighbor not in [p["to"] for p in path] and neighbor != start_table:
                    new_path = path + [edge]
                    queue.append((neighbor, new_path))
        
        return paths

class JoinRanker:
    """
    Ranks join paths based on length and memory boost.
    """

    def __init__(self, memory=None):
        self.memory = memory

    def rank_join_paths(self, paths: list[list[dict]]) -> list[list[dict]]:
        """
        Ranks join paths. Shorter is better.
        """
        def score(path):
            s = -len(path)
            if self.memory:
                # Extract table names for memory lookup
                table_path = [p["to"] for p in path]
                s += self.memory.get_path_boost(table_path)
            return s

        return sorted(paths, key=score, reverse=True)
