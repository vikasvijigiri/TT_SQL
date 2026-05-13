from typing import Any, Dict, List
import pandas as pd
from src.utils.logger import logger

def analyze_result(result_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Statistical analysis of query results.
    """
    anomalies = []
    confidence_score = 1.0
    
    if not result_rows:
        return {
            "confidence_score": 0.6,
            "anomalies": [{"type": "empty_result", "message": "Query returned 0 rows."}]
        }
    
    try:
        df = pd.DataFrame(result_rows)
        total_rows = len(df)
        
        # 1. High Duplication Ratio
        unique_rows = len(df.drop_duplicates())
        dupe_ratio = 1.0 - (unique_rows / total_rows)
        
        if dupe_ratio > 0.5:
            confidence_score -= (0.3 * dupe_ratio)
            anomalies.append({
                "type": "high_duplication_ratio",
                "message": f"Suspicious duplication detected: {round(dupe_ratio*100)}% of rows are duplicates."
            })
            
        # 2. Null Ratio
        for col in df.columns:
            null_count = df[col].isnull().sum()
            null_ratio = null_count / total_rows
            
            if null_ratio > 0.7:
                confidence_score -= 0.1
                anomalies.append({
                    "type": "high_null_ratio",
                    "message": f"Column '{col}' is largely NULL ({round(null_ratio*100)}%)."
                })
                
    except Exception as e:
        logger.warning(f"[DataIQ] Statistical analysis failed: {str(e)}")
        
    return {
        "confidence_score": round(max(0.0, confidence_score), 2),
        "anomalies": anomalies
    }
