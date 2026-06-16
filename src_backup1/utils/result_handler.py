import os
import pandas as pd
from typing import List, Dict, Any
from src.utils.logger import logger

def save_results(db_name: str, sql: str, rows: List[Dict[str, Any]], output_dir: str = "results"):
    """
    Saves the SQL query and the resulting rows to files.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        db_dir = os.path.join(output_dir, db_name)
        os.makedirs(db_dir, exist_ok=True)
        
        # Save SQL
        sql_path = os.path.join(db_dir, "query.sql")
        with open(sql_path, "w") as f:
            f.write(sql)
            
        # Save CSV
        if rows:
            csv_path = os.path.join(db_dir, "results.csv")
            df = pd.DataFrame(rows)
            df.to_csv(csv_path, index=False)
            logger.info(f"Results saved to {csv_path}")
        else:
            logger.warning("No rows to save for CSV.")
            
    except Exception as e:
        logger.error(f"Failed to save results: {e}")
