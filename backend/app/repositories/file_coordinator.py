import os
import json
from pathlib import Path
from typing import Optional, Union, List, Any, Dict
from app.core.logger import Logger
from app.schemas.agent_state import AgentState
from app.repositories.paths import InstancePaths

class FileCoordinator:
    """
    Coordinates file-based communication between agents.
    Uses centralized paths from paths.py module.
    """
    def __init__(self, results_dir: Optional[Union[str, Path]] = None, logs_dir: Optional[Union[str, Path]] = None, user_slug: Optional[str] = None, project_slug: Optional[str] = None):
        self.results_dir = Path(results_dir) if results_dir else None
        self.logs_dir = Path(logs_dir) if logs_dir else None
        self.user_slug = user_slug
        self.project_slug = project_slug

    def get_sql_path(self, instance_id: str, model_name: str = None) -> str:
        from app.repositories.paths import get_model_results_dir, InstancePaths
        from app.core.settings import settings
        m_name = model_name or settings.LLM_MODEL or "default"
        model_dir = get_model_results_dir(m_name, user_slug=self.user_slug, project_slug=self.project_slug)
        return str(InstancePaths.sql(instance_id, model_dir))

    def get_log_path(self, instance_id: str, model_name: str = None) -> str:
        from app.repositories.paths import get_model_results_dir, InstancePaths
        from app.core.settings import settings
        m_name = model_name or settings.LLM_MODEL or "default"
        model_dir = get_model_results_dir(m_name, user_slug=self.user_slug, project_slug=self.project_slug)
        return str(InstancePaths.log(instance_id, model_dir))



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

    def write_csv(self, instance_id: str, rows: List[List[Any]], columns: List[str], model_name: str = None):
        import csv
        from app.repositories.paths import get_model_results_dir, InstancePaths
        from app.core.settings import settings
        m_name = model_name or settings.LLM_MODEL or "default"
        model_dir = get_model_results_dir(m_name, user_slug=self.user_slug, project_slug=self.project_slug)
        path = str(InstancePaths.csv(instance_id, model_dir))
        
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if columns: writer.writerow(columns)
                writer.writerows(rows)
        except Exception as e:
            print(f"Error writing CSV: {e}")

    # --- Private Methods ---

    def _format_schema_as_markdown(self, schema_info: Dict[str, Any]) -> str:
        md_lines = ["Database Schema Context\n"]
        for table_name, table_data in schema_info.items():
            md_lines.append(f"Table: {table_name}")
            columns = table_data.get("columns", [])
            for col in columns:
                md_lines.append(f"{col.get('column_name', 'N/A')}, {col.get('type', 'N/A')}, {col.get('description', 'N/A').replace('|', ' ')}")
            md_lines.append("")
        return "\n".join(md_lines)
