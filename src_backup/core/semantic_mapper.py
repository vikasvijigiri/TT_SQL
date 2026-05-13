from core.logger import Logger

class StructureAwareMapper:
    """
    Maps intent tasks to schema candidates using semantic and structural awareness.
    """

    def __init__(self, memory=None):
        self.memory = memory

    def _extract_task_values(self, task: dict) -> list[str]:
        """Extracts literal values from a task for matching."""
        values = []
        task_val = task.get("value")
        if isinstance(task_val, dict):
            # If it's a filter
            if "value" in task_val:
                v = task_val["value"]
                if isinstance(v, list): values.extend([str(i).lower() for i in v])
                else: values.append(str(v).lower())
            
            # If it's an aggregation step
            if "input" in task_val:
                values.append(str(task_val["input"]).lower())
            if "field" in task_val:
                values.append(str(task_val["field"]).lower())
        else:
            values.append(str(task_val).lower())
        return [v for v in values if v]

    def map(self, tasks: list[dict], candidates: list[dict]) -> list[dict]:
        """
        Maps each task to the best schema candidate.
        Scoring (Step 7):
          final_score = 0.4 * value_score + 0.2 * json_score + 0.2 * array_score + 0.1 * statistical_score + 0.1 * name_score
        STRICT RULE: if no value/json/array match -> reject candidate
        """
        mappings = []

        for task in tasks:
            task_values = self._extract_task_values(task)
            best_candidate = None
            max_score = -1.0

            for cand in candidates:
                col_meta = cand["meta"]
                col_type = str(col_meta.get("type", "")).upper()
                col_name = cand["column"].lower()
                
                # 1. Value Score
                value_score = 0.0
                sample_values = col_meta.get("sample_values", [])
                
                # Check if any task value matches sample values
                for tv in task_values:
                    if any(tv in str(v).lower() for v in sample_values):
                        value_score = 1.0
                        break
                    # Also check if col_name is in task (for aggregations like COUNT(id))
                    if col_name in tv:
                        value_score = 0.8
                        break
                
                # 2. JSON Score (Snowflake VARIANT or JSON type)
                json_score = 0.0
                if any(t in col_type for t in ["VARIANT", "JSON", "OBJECT"]):
                    v_keys = col_meta.get("variant_keys", [])
                    for tv in task_values:
                        if any(tv in str(k).lower() for k in v_keys):
                            json_score = 1.0
                            break
                
                # 3. Array Score
                array_score = 0.0
                if "ARRAY" in col_type:
                    array_score = 0.5
                
                # 4. Statistical Score (from SchemaIndexer)
                statistical_score = col_meta.get("statistical_score", 0.0)
                
                # 5. Name Score
                name_score = cand["score"] / 10.0 # Normalize retrieval score
                
                # 6. Fallback Rule (Relaxed): If it's a very strong name match, allow it even without sample
                if value_score == 0 and json_score == 0 and array_score == 0:
                    if name_score < 0.8: # Threshold for name match
                        continue
                    else:
                        value_score = 0.1 # Small boost for name match
                
                final_score = (
                    0.4 * value_score +
                    0.2 * json_score +
                    0.2 * array_score +
                    0.1 * statistical_score +
                    0.1 * name_score
                )
                
                if final_score > max_score:
                    max_score = final_score
                    best_candidate = {
                        "task": task,
                        "mapping": cand,
                        "score": final_score
                    }
            
            if best_candidate:
                mappings.append(best_candidate)
        
        return mappings
