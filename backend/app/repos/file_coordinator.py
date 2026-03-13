import os
import json
from app.services.logger import Logger
from app.models.agent_state import AgentState
from typing import Optional, Union, List, Any, Dict
from app.models.paths import InstancePaths

class FileCoordinator:
    """
    Coordinates file-based communication between agents.
    Uses centralized paths from paths.py module.
    """
    def __init__(self, results_dir: Optional[Union[str, Path]] = None, logs_dir: Optional[Union[str, Path]] = None):
        self.results_dir = Path(results_dir) if results_dir else None
        self.logs_dir = Path(logs_dir) if logs_dir else None

    def get_sql_path(self, instance_id: str, model_name: str = "default_model") -> str:
        return str(InstancePaths.sql(instance_id, model_name, base_dir=self.results_dir))

    def get_log_path(self, instance_id: str, model_name: str = "default_model") -> str:
        return str(InstancePaths.log(instance_id, model_name, base_dir=self.logs_dir))



    def write_sql(self, instance_id: str, sql: Union[str, List[str]], model_name: str = "default_model"):
        path = self.get_sql_path(instance_id, model_name)
        with open(path, "w", encoding="utf-8") as f:
            if isinstance(sql, list):
                f.write("\n".join(sql))
            else:
                f.write(sql)

    def read_sql(self, instance_id: str, model_name: str = "default_model") -> Optional[str]:
        path = self.get_sql_path(instance_id, model_name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def write_csv(self, instance_id: str, rows: List[List[Any]], columns: List[str], model_name: str = "default_model"):
        """Write execution results to CSV."""
        import csv
        path = str(InstancePaths.csv(instance_id, model_name, base_dir=self.results_dir))
        
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if columns:
                    writer.writerow(columns)
                writer.writerows(rows)
        except Exception as e:
            print(f"Error writing CSV: {e}")

    def _format_schema_as_markdown(self, schema_info: Dict[str, Any]) -> str:
        """Converts a schema dictionary into a simple text representation without special characters."""
        md_lines = ["Database Schema Context\n"]
        
        for table_name, table_data in schema_info.items():
            md_lines.append(f"Table: {table_name}")
            
            columns = table_data.get("columns", [])
            for col in columns:
                name = col.get("column_name", "N/A")
                ctype = col.get("type", "N/A")
                desc = col.get("description", "N/A").replace("|", " ")
                md_lines.append(f"{name}, {ctype}, {desc}")
            md_lines.append("") # Spacer
            
        return "\n".join(md_lines)
