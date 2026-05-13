import os
import pickle
import json
import networkx as nx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from rapidfuzz import fuzz
from src.utils.logger import logger

@dataclass
class ColumnNode:
    full_path: str  # DB.SCHEMA.TABLE.COLUMN
    table: str
    column: str
    data_type: str
    sample_values: List[Any] = field(default_factory=list)
    description: str = ""
    domain_tags: List[str] = field(default_factory=list)

@dataclass
class JoinStep:
    left_table: str
    right_table: str
    left_col: str
    right_col: str
    join_type: str = "LEFT"

class SchemaGraphBuilder:
    """
    Builds a FULL column-level schema graph for high-precision grounding and join inference.
    """
    
    def __init__(self, schema_with_samples: Dict[str, Dict[str, Dict[str, Any]]], db_name: str):
        self.schema = schema_with_samples
        self.db_name = db_name
        self.graph = nx.Graph()
        self.cache_path = f"schema_cache/graph_{db_name}.pkl"
        os.makedirs("schema_cache", exist_ok=True)
        
    def _get_domain_tags(self, table: str, column: str) -> List[str]:
        """Auto-tags columns based on name patterns."""
        tags = []
        name_lower = f"{table}.{column}".lower()
        
        if any(x in name_lower for x in ["dicom", "image", "modality", "sop", "instance"]):
            tags.append("dicom")
            tags.append("imaging")
        if any(x in name_lower for x in ["tcga", "clinical", "patient", "tumor", "specimen"]):
            tags.append("clinical")
        if any(x in name_lower for x in ["pathology", "slide", "tissue", "stain"]):
            tags.append("pathology")
            
        return tags

    def build(self) -> nx.Graph:
        """
        Builds the full column-level graph from the schema metadata.
        """
        logger.info(f"Building full schema graph for {self.db_name}...")
        
        # 1. Add all column nodes
        for table_fqn, table_data in self.schema.items():
            cols_list = table_data.get("columns", [])
            samples_list = table_data.get("sample", [])
            
            for col_info in cols_list:
                col_name = col_info.get("column_name")
                if not col_name: continue
                
                node_id = f"{table_fqn}.{col_name}"
                
                # Try to find samples for this column if available
                col_samples = []
                for s in samples_list[:5]:
                    if isinstance(s, dict) and col_name in s:
                        col_samples.append(s[col_name])

                node = ColumnNode(
                    full_path=node_id,
                    table=table_fqn,
                    column=col_name,
                    data_type=col_info.get("type", "string"),
                    sample_values=col_samples,
                    description=col_info.get("description", ""),
                    domain_tags=self._get_domain_tags(table_fqn, col_name)
                )
                
                self.graph.add_node(node_id, data=node)
        
        # 2. Add edges (FK candidates and similarities)
        nodes = list(self.graph.nodes(data=True))
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                id_a, data_a = nodes[i]
                id_b, data_b = nodes[j]
                node_a: ColumnNode = data_a["data"]
                node_b: ColumnNode = data_b["data"]
                
                # Rule: Same name across tables (Strong FK candidate)
                if node_a.column == node_b.column and node_a.table != node_b.table:
                    self.graph.add_edge(id_a, id_b, weight=0.9, type="fk_candidate")
                    
                # Rule: Same type + Overlapping samples (Weak candidate)
                elif node_a.data_type == node_b.data_type and node_a.table != node_b.table:
                    # Simple overlap check for small sample sets
                    overlap = set(str(v).lower() for v in node_a.sample_values) & set(str(v).lower() for v in node_b.sample_values)
                    if overlap and len(overlap) >= 2:
                        self.graph.add_edge(id_a, id_b, weight=0.6, type="sample_overlap")
        
        # 3. Add edges from query_log.json (Weight 0.8)
        query_log_path = "query_log.json"
        if os.path.exists(query_log_path):
            try:
                with open(query_log_path, "r") as f:
                    logs = json.load(f)
                    for log in logs:
                        cols = log.get("columns", [])
                        for i in range(len(cols)):
                            for j in range(i + 1, len(cols)):
                                if self.graph.has_node(cols[i]) and self.graph.has_node(cols[j]):
                                    self.graph.add_edge(cols[i], cols[j], weight=0.8, type="query_cooccurrence")
            except Exception as e:
                logger.warning(f"Failed to load query_log.json: {e}")
        
        # 4. Save to cache
        with open(self.cache_path, "wb") as f:
            pickle.dump(self.graph, f)
            
        logger.info(f"Schema graph built with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")
        return self.graph

    def build_or_load(self, force_rebuild: bool = False) -> nx.Graph:
        """Loads from cache or builds if missing."""
        if not force_rebuild and os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "rb") as f:
                    self.graph = pickle.load(f)
                logger.info(f"Loaded schema graph from {self.cache_path}")
                return self.graph
            except Exception as e:
                logger.warning(f"Failed to load schema graph cache: {e}. Rebuilding...")
        
        return self.build()

    def get_candidates(self, raw_field: str, value: Any = None, top_k: int = 20) -> List[ColumnNode]:
        """
        Fast pre-filtering for column candidates using exact and fuzzy matching.
        """
        scored_candidates = []
        raw_field_lower = raw_field.lower()
        
        # Check domain tags first
        relevant_tags = []
        if any(x in raw_field_lower for x in ["clinical", "patient", "tumor"]): relevant_tags.append("clinical")
        if any(x in raw_field_lower for x in ["pathology", "slide", "tissue"]): relevant_tags.append("pathology")
        if any(x in raw_field_lower for x in ["imaging", "dicom", "image"]): relevant_tags.append("imaging")

        for node_id, data in self.graph.nodes(data=True):
            node: ColumnNode = data["data"]
            score = 0.0
            
            # 1. Exact match on column name
            if raw_field_lower == node.column.lower():
                score += 1.0
                
            # 2. Fuzzy match on column name and description
            fuzzy_score = fuzz.partial_ratio(raw_field_lower, node.column.lower()) / 100.0
            if fuzzy_score > 0.7:
                score = max(score, fuzzy_score)
                
            # 3. Domain tag boost
            if any(tag in node.domain_tags for tag in relevant_tags):
                score += 0.2
                
            if score > 0:
                scored_candidates.append((node, score))
        
        # Sort by score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in scored_candidates[:top_k]]

    def resolve_join_path(self, table_a: str, table_b: str, max_hops: int = 3) -> List[JoinStep]:
        """
        Resolves a join path between two tables using BFS on FK edges, supporting bridge tables.
        """
        if table_a == table_b:
            return []
            
        # Get all column nodes for both tables
        def get_table_cols(table):
            return [n for n, d in self.graph.nodes(data=True) if d["data"].table == table]

        # BFS on tables
        queue = [(table_a, [])]
        visited_tables = {table_a}
        
        while queue:
            current_table, current_path = queue.pop(0)
            
            if len(current_path) >= max_hops:
                continue
                
            # Find all neighbors of current_table across FK edges
            current_cols = get_table_cols(current_table)
            
            for col_a in current_cols:
                for col_b in self.graph.neighbors(col_a):
                    edge_data = self.graph.get_edge_data(col_a, col_b)
                    if edge_data.get("type") != "fk_candidate":
                        continue
                        
                    neighbor_table = self.graph.nodes[col_b]["data"].table
                    if neighbor_table == table_b:
                        # Found target!
                        new_step = JoinStep(
                            left_table=current_table,
                            right_table=neighbor_table,
                            left_col=col_a.split(".")[-1],
                            right_col=col_b.split(".")[-1]
                        )
                        return current_path + [new_step]
                        
                    if neighbor_table not in visited_tables:
                        visited_tables.add(neighbor_table)
                        new_step = JoinStep(
                            left_table=current_table,
                            right_table=neighbor_table,
                            left_col=col_a.split(".")[-1],
                            right_col=col_b.split(".")[-1]
                        )
                        queue.append((neighbor_table, current_path + [new_step]))
        
        return []
