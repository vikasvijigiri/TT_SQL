from core.logger import Logger
import json

class Retriever:
    """
    Retrieves top-K schema elements based on token match, value match, and memory boost.
    """

    def __init__(self, schema_info: dict, memory=None):
        self.schema_info = schema_info
        self.memory = memory

    def retrieve(self, query: str, top_k: int = 100) -> list[dict]:
        """
        Retrieves schema candidates. 
        Score (Step 3): 3 * value_match + 1 * token_match + memory_boost
        """
        candidates = []
        query_tokens = set(query.lower().replace("_", " ").replace(".", " ").split())

        for table_name, table_data in self.schema_info.items():
            # Get table-level sample for column-level fallback
            table_sample = []
            if "sample" in table_data:
                raw_sample = table_data["sample"]
                try:
                    table_sample = json.loads(raw_sample) if isinstance(raw_sample, str) else raw_sample
                except: pass

            for col in table_data.get("columns", []):
                col_name = col["column_name"]
                
                # 1. Token Match
                col_tokens = set(col_name.lower().replace("_", " ").split())
                token_match = len(query_tokens & col_tokens)
                
                # 2. Value Match
                value_match = 0
                sample_values = col.get("sample_values", [])
                if not sample_values and table_sample:
                    sample_values = [str(row.get(col_name)) for row in table_sample if row.get(col_name) is not None]

                for val in sample_values:
                    val_str = str(val).lower()
                    if any(token in val_str for token in query_tokens if len(token) > 2):
                        value_match = 1
                        break
                
                # 3. Memory Boost
                memory_boost = 0
                if self.memory:
                    memory_boost = self.memory.get_boost(query, f"{table_name}.{col_name}")
                
                score = 3 * value_match + 1 * token_match + memory_boost
                
                # Even if score is 0, we might want to include it if it's a PK or FK
                if col.get("pk") or col.get("fk"):
                    score += 0.5

                if score > 0:
                    candidates.append({
                        "table": table_name,
                        "column": col_name,
                        "score": score,
                        "meta": col
                    })

        # Sort by score and return top-K
        candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)
        return candidates[:top_k]
