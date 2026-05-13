from typing import List
from src.core.models import ColumnMapping, ExecutionResult

class ConfidenceEstimator:
    def estimate(self, intent, mappings, plan, row_count, error) -> float:
        if not mappings: return 0.0
        
        avg_mapping_conf = sum(m.confidence for m in mappings) / len(mappings)
        
        confidence = avg_mapping_conf
        
        if error:
            confidence *= 0.1
        elif row_count == 0:
            confidence *= 0.5
            
        return min(confidence, 1.0)
