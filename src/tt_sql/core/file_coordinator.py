import os
import json
from typing import Optional, Union, List, Any, Dict
from .paths import InstancePaths

class FileCoordinator:
    """
    Coordinates file-based communication between agents.
    Uses centralized paths from paths.py module.
    """
    def __init__(self):
        # Directories are created dynamically by paths.initialize_directories()
        pass

    def get_sql_path(self, instance_id: str, model_name: str = "default_model") -> str:
        return str(InstancePaths.sql(instance_id, model_name))

    def get_plan_path(self, instance_id: str, model_name: str = "default_model") -> str:
        return str(InstancePaths.plan(instance_id, model_name))



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

    def write_plan(self, instance_id: str, plan_steps: List[str], model_name: str = "default_model"):
        """Write action plan to markdown file."""
        path = self.get_plan_path(instance_id, model_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Action Plan\n\n")
            for step in plan_steps:
                f.write(f"- {step}\n")

    def read_plan(self, instance_id: str, model_name: str = "default_model") -> Optional[str]:
        """Read action plan from markdown file."""
        path = self.get_plan_path(instance_id, model_name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return None


    

    


    def write_csv(self, instance_id: str, rows: List[List[Any]], columns: List[str], model_name: str = "default_model"):
        """Write execution results to CSV."""
        import csv
        path = str(InstancePaths.csv(instance_id, model_name))
        
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if columns:
                    writer.writerow(columns)
                writer.writerows(rows)
        except Exception as e:
            print(f"Error writing CSV: {e}")

    def write_schema(self, instance_id: str, schema_info: Dict[str, Any], model_name: str = "default_model"):
        """Write schema JSON for an instance."""
        path = str(InstancePaths.schema(instance_id, model_name))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(schema_info, f, indent=2)

    def read_schema(self, instance_id: str, model_name: str = "default_model") -> Optional[Dict[str, Any]]:
        """Read schema JSON for an instance."""
        path = str(InstancePaths.schema(instance_id, model_name))
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
