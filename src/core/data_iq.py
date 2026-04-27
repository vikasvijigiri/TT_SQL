from typing import Any, Dict, List
from core.state import ExecutionResult
from core.logger import Logger

def analyze_result(result: ExecutionResult) -> Dict[str, Any]:
    """
    TASK 7: ADD RESULT VALIDATION (DATAIQ) WITHOUT HARDCODING
    Checks must be statistical, not rule-based:
    - row_count == 0 → low confidence
    - high duplication ratio → suspicious
    - null ratio per column
    """
    anomalies = []
    confidence_score = 1.0
    
    if result.error_message:
        return {
            "confidence_score": 0.0,
            "anomalies": [{"type": "execution_error", "message": result.error_message}]
        }
    
    # 1. Row Count Check
    if result.row_count == 0:
        confidence_score -= 0.4 # Reduced confidence but not zero
        anomalies.append({"type": "empty_result", "message": "Query returned 0 rows (potential low confidence)."})
    
    # Use the result's internal dataframe conversion for analysis
    try:
        df = result.rows_to_df()
        
        if not df.empty:
            # 2. High Duplication Ratio
            total_rows = len(df)
            unique_rows = len(df.drop_duplicates())
            dupe_ratio = 1.0 - (unique_rows / total_rows)
            
            if dupe_ratio > 0.5:
                confidence_score -= (0.3 * dupe_ratio)
                anomalies.append({
                    "type": "high_duplication_ratio",
                    "ratio": round(dupe_ratio, 2),
                    "message": f"Suspicious duplication detected: {round(dupe_ratio*100)}% of rows are duplicates."
                })
                
            # 3. Null Ratio per column
            for col in df.columns:
                null_count = df[col].isnull().sum()
                null_ratio = null_count / total_rows
                
                if null_ratio > 0.7: # Threshold for high nullity
                    confidence_score -= 0.1
                    anomalies.append({
                        "type": "high_null_ratio",
                        "column": col,
                        "ratio": round(null_ratio, 2),
                        "message": f"Column '{col}' is largely NULL ({round(null_ratio*100)}%)."
                    })
                    
    except Exception as e:
        Logger.log(f"[DataIQ] Statistical analysis failed: {str(e)}", level="WARN")
        # Don't crash the pipeline if analysis fails
        
    confidence_score = max(0.0, min(1.0, confidence_score))
    
    analysis = {
        "confidence_score": round(confidence_score, 2),
        "anomalies": anomalies
    }
    
    # Structured Logs
    Logger.log(f"\n[DataIQ] Analysis Result")
    Logger.log(f"  - confidence_score: {analysis['confidence_score']}")
    if anomalies:
        for a in anomalies:
            Logger.log(f"  - anomaly [{a['type']}]: {a['message']}")
    else:
        Logger.log("  - No anomalies detected. High confidence.")
            
def generate_eda_report(result: ExecutionResult) -> str:
    """Generates a markdown report for agent context based on statistical analysis."""
    if not result or result.error_message:
        return "No valid data for EDA."
    
    try:
        df = result.rows_to_df()
        if df.empty:
            return "Result set is empty."
            
        report = [
            "### 📋 DATA PROFILE (Statistical)",
            f"- **Rows**: {len(df)}",
            f"- **Columns**: {len(df.columns)}",
            ""
        ]
        
        # Column analysis
        report.append("| Column | Type | Non-Null | Unique | Sample |")
        report.append("| :--- | :--- | :--- | :--- | :--- |")
        for col in df.columns:
            dtype = str(df[col].dtype)
            count = int(df[col].count())
            unique = int(df[col].nunique())
            sample = str(df[col].dropna().iloc[0])[:20] if not df[col].dropna().empty else "N/A"
            report.append(f"| {col} | {dtype} | {count} | {unique} | {sample} |")
        
        return "\n".join(report)
    except Exception as e:
        return f"EDA report generation failed: {str(e)}"
