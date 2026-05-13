from sentence_transformers import SentenceTransformer
from typing import Dict, List, Tuple, Any

class SchemaIndex:
    """
    Value-aware Schema Index. 
    Stores column names, embeddings, and sample values for high-precision grounding.
    """
    def __init__(self, schema: Dict[str, Dict[str, Dict[str, Any]]]):
        # schema format: { table: { col: { "sample_values": [], ... } } }
        self.schema = schema
        self.columns: List[Tuple[str, str]] = []
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.column_info = {}

        # Extract columns and metadata
        all_col_names = []
        for table, cols in schema.items():
            for col, meta in cols.items():
                self.columns.append((table, col))
                all_col_names.append(col)
                
                self.column_info[f"{table}.{col}"] = {
                    "table": table,
                    "column": col,
                    "samples": meta.get("sample_values", [])
                }

        # Batch encode all columns
        print(f"Grounding: Encoding {len(all_col_names)} schema columns...")
        encoded_vecs = self.model.encode(all_col_names, show_progress_bar=False)
        
        # Map embeddings back to column_info
        for i, (table, col) in enumerate(self.columns):
            self.column_info[f"{table}.{col}"]["embedding"] = encoded_vecs[i]
