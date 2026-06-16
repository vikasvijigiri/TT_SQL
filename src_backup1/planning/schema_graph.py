from typing import List, Dict, Set, Optional, Tuple, Any
from collections import deque
from src.indexing.schema_indexer import SchemaIndexer
from src.utils.logger import logger

class SchemaGraph:
    def __init__(self, indexer: SchemaIndexer):
        self.indexer = indexer
        self.adj: Dict[str, Set[str]] = {}
        self.edges: Dict[Tuple[str, str], Any] = {} # (t1, t2) -> join_col

    def build(self):
        # The new Indexer has self.columns: Dict[fqn, CandidateColumn]
        # and self.columns.values() contains table names in c.table
        
        # Get unique table names
        tables = list(set(c.table for c in self.indexer.columns.values()))
        
        # Pre-group columns by table for efficiency
        table_cols = {}
        for t in tables:
            table_cols[t] = {c.column for c in self.indexer.columns.values() if c.table == t}

        for i in range(len(tables)):
            for j in range(i + 1, len(tables)):
                t1, t2 = tables[i], tables[j]
                
                cols1 = table_cols[t1]
                cols2 = table_cols[t2]
                
                # Generic columns that should NEVER be used for joins
                generic = {
                    'id', 'name', 'type', 'created_at', 'updated_at', 'date', 'time', 'timestamp', 
                    'index', 'row_num', 'location', 'title', 'access', 'description', 'updated',
                    'license_url', 'license_long_name', 'license_short_name',
                    'transfersyntaxuid', 'sopclassuid', 'implementationclassuid', 'implementationversionname',
                    'specificcharacterset', 'mediastoragesopclassuid', 'mediastoragesopinstanceuid',
                    'instancecreationdate', 'instancecreationtime', 'instancenumber',
                    'rows', 'columns', 'bitsallocated', 'bitsstored', 'highbit', 'pixelrepresentation',
                    'samplesperpixel', 'planarconfiguration', 'photometricinterpretation'
                }
                
                shared = cols1.intersection(cols2)
                shared = {c for c in shared if c.lower() not in generic}
                
                synonyms = [
                    (['case_id', 'idc_case_id', 'case_gdc_id', 'case_barcode'], 'case_id'),
                    (['patient_id', 'patient_barcode', 'submitter_id'], 'patient_id'),
                    (['series_instance_uid', 'series_uid', 'crdc_series_uuid'], 'series_instance_uid'),
                    (['study_instance_uid', 'study_uid', 'crdc_study_uuid'], 'study_instance_uid')
                ]
                
                join_col = None
                if shared:
                    priority_shared = sorted(
                        list(shared),
                        key=lambda x: (
                            0 if 'UID' in x.upper() else 
                            1 if x.upper().endswith('ID') or '_ID' in x.upper() else 
                            2
                        )
                    )
                    join_col = priority_shared[0]
                else:
                    for syn_list, canonical in synonyms:
                        match1 = next((c for c in cols1 if c.lower() in syn_list), None)
                        match2 = next((c for c in cols2 if c.lower() in syn_list), None)
                        if match1 and match2:
                            join_col = (match1, match2)
                            break
                
                if join_col:
                    self._add_edge(t1, t2, join_col)
        
        logger.info(f"Built Schema Graph with {len(self.adj)} nodes.")

    def _add_edge(self, t1: str, t2: str, col: Any):
        if t1 not in self.adj: self.adj[t1] = set()
        if t2 not in self.adj: self.adj[t2] = set()
        self.adj[t1].add(t2)
        self.adj[t2].add(t1)
        self.edges[(t1, t2)] = col
        if isinstance(col, tuple):
            self.edges[(t2, t1)] = (col[1], col[0])
        else:
            self.edges[(t2, t1)] = col

    def find_path(self, start_table: str, target_tables: Set[str]) -> List[Dict[str, Any]]:
        if not target_tables:
            return []
            
        path_elements = []
        visited = {start_table}
        queue = deque([(start_table, [])])
        
        found_tables = {start_table}
        
        while queue and found_tables != target_tables.union({start_table}):
            current, path = queue.popleft()
            
            for neighbor in self.adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    join_info = self.edges[(current, neighbor)]
                    
                    if isinstance(join_info, tuple):
                        on_clause = {"left": join_info[0], "right": join_info[1]}
                    else:
                        on_clause = join_info
                    
                    new_path = path + [{"table": neighbor, "from": current, "on": on_clause}]
                    queue.append((neighbor, new_path))
                    
                    if neighbor in target_tables:
                        found_tables.add(neighbor)
                        for segment in new_path:
                            if not any(s['table'] == segment['table'] for s in path_elements):
                                path_elements.append(segment)
                                
        return path_elements
