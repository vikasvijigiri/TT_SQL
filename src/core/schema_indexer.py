import json
from core.logger import Logger

class SchemaIndexer:
    """
    Indexes database schema and computes statistical metadata for better grounding and ranking.
    """

    def __init__(self, service):
        self.service = service

    def compute_column_stats(self, table_name: str, column_name: str) -> dict:
        """
        Computes distinct_count and null_ratio for a given column.
        """
        try:
            # Use double quotes for identifiers to handle case-sensitivity and special characters
            quoted_table = f'"{table_name}"' if "." not in table_name else table_name
            quoted_column = f'"{column_name}"'
            
            # SQL for distinct count and null ratio
            # Using a single query to minimize round-trips
            query = f"""
            SELECT 
                COUNT(DISTINCT {quoted_column}) as distinct_count,
                COUNT(*) as total_count,
                SUM(CASE WHEN {quoted_column} IS NULL THEN 1 ELSE 0 END) as null_count
            FROM {quoted_table}
            """
            
            result = self.service.execute_query(query)
            if result.error_message or not result.rows:
                return {"distinct_count": 0, "null_ratio": 0.0}
            
            row = result.rows[0]
            distinct_count = row[0] or 0
            total_count = row[1] or 0
            null_count = row[2] or 0
            
            null_ratio = null_count / total_count if total_count > 0 else 0.0
            
            return {
                "distinct_count": distinct_count,
                "null_ratio": null_ratio
            }
        except Exception as e:
            Logger.log(f"Error computing stats for {table_name}.{column_name}: {str(e)}", level="WARN")
            return {"distinct_count": 0, "null_ratio": 0.0}

    def statistical_score(self, meta: dict) -> float:
        """
        Computes a statistical score based on metadata.
        Rule (Step 4):
        - if distinct_count < 100: score += 1
        - if null_ratio < 0.5: score += 1
        """
        score = 0
        if meta.get("distinct_count", 0) < 100:
            score += 1
        if meta.get("null_ratio", 1.0) < 0.5:
            score += 1
        return float(score)

    def _extract_keys_recursive(self, data, prefix="", depth=0, max_depth=3):
        """Recursively extracts keys from nested dictionaries/lists."""
        if depth > max_depth:
            return set()
        
        keys = set()
        if isinstance(data, dict):
            for k, v in data.items():
                full_key = f"{prefix}.{k}" if prefix else k
                keys.add(full_key)
                keys.update(self._extract_keys_recursive(v, full_key, depth + 1, max_depth))
        elif isinstance(data, list):
            for item in data[:5]: # Only check first 5 items to avoid explosion
                keys.update(self._extract_keys_recursive(item, prefix, depth, max_depth)) # Don't increment depth for list traversal if same level
        return keys

    def discover_variant_keys(self, table_data: dict) -> dict[str, list[str]]:
        """
        Discovers keys within VARIANT/OBJECT/JSON columns by inspecting sample rows.
        """
        variant_keys = {}
        samples = table_data.get("sample", [])
        if not samples:
            return variant_keys
            
        for col in table_data.get("columns", []):
            col_name = col["column_name"]
            col_type = str(col.get("type", "")).upper()
            
            # Heuristic: Check if column likely contains JSON
            is_variant = any(t in col_type for t in ["VARIANT", "OBJECT", "ARRAY", "JSON"])
            
            if is_variant:
                all_keys = set()
                for row in samples:
                    val = row.get(col_name)
                    if not val: continue
                    
                    try:
                        # Try to parse if string
                        if isinstance(val, str) and (val.strip().startswith("{") or val.strip().startswith("[")):
                            data = json.loads(val)
                        else:
                            data = val
                            
                        all_keys.update(self._extract_keys_recursive(data))
                    except:
                        pass
                
                if all_keys:
                    variant_keys[col_name] = sorted(list(all_keys))
        
        return variant_keys

    def index_schema(self, schema_info: dict, skip_stats: bool = False) -> dict:
        """
        Enriches schema_info with statistical metadata and variant keys.
        """
        for table_name, table_data in schema_info.items():
            # 1. Discover variant keys from samples
            v_keys = self.discover_variant_keys(table_data)
            
            for col in table_data.get("columns", []):
                col_name = col["column_name"]
                
                # 2. Compute stats (if service is active and not skipped)
                if self.service and not skip_stats:
                    stats = self.compute_column_stats(table_name, col_name)
                    col.update(stats)
                    col["statistical_score"] = self.statistical_score(stats)
                
                # 3. Inject variant keys
                if col_name in v_keys:
                    col["variant_keys"] = v_keys[col_name]
                    
        return schema_info
