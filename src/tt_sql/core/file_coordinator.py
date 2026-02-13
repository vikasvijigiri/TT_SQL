import os
import json
from typing import Optional, Union, List, Any
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

    def get_feedback_path(self, instance_id: str, model_name: str = "default_model") -> str:
        return str(InstancePaths.feedback(instance_id, model_name))

    def get_schema_path(self, instance_id: str, model_name: str = "default_model") -> str:
        return str(InstancePaths.schema(instance_id, model_name))

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

    def write_feedback(self, instance_id: str, feedback_data: dict, model_name: str = "default_model"):
        path = self.get_feedback_path(instance_id, model_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(feedback_data, f, indent=2)

    def read_feedback(self, instance_id: str, model_name: str = "default_model") -> Optional[dict]:
        path = self.get_feedback_path(instance_id, model_name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def write_schema(self, instance_id: str, schema_info: dict, model_name: str = "default_model"):
        """Write schema information for an instance."""
        path = self.get_schema_path(instance_id, model_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(schema_info, f, indent=2)

    def read_schema(self, instance_id: str, model_name: str = "default_model") -> Optional[dict]:
        """Read schema information for an instance."""
        path = self.get_schema_path(instance_id, model_name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def write_subtasks(self, instance_id: str, subtasks_list: List[Any], model_name: str = "default_model"):
        """Write subtask history for an instance."""
        path = str(InstancePaths.subtasks(instance_id, model_name))
        # Handle Pydantic models in the list
        serializable_data = [
            st.model_dump() if hasattr(st, "model_dump") else st 
            for st in subtasks_list
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, indent=2)
    
    def write_intent(self, instance_id: str, intent_data: dict, model_name: str = "default_model"):
        """Write intent classification results for an instance."""
        path = str(InstancePaths.intent(instance_id, model_name))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(intent_data, f, indent=2)
    
    def read_intent(self, instance_id: str, model_name: str = "default_model") -> Optional[dict]:
        """Read intent classification results for an instance."""
        path = str(InstancePaths.intent(instance_id, model_name))
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    def write_context(self, instance_id: str, context_data: dict, model_name: str = "default_model"):
        """Write context enrichment results for an instance."""
        path = str(InstancePaths.context(instance_id, model_name))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(context_data, f, indent=2)
    
    def read_context(self, instance_id: str, model_name: str = "default_model") -> Optional[dict]:
        """Read context enrichment results for an instance."""
        path = str(InstancePaths.context(instance_id, model_name))
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    def write_plan(self, instance_id: str, plan_data: dict, model_name: str = "default_model"):
        """Write execution plan for an instance."""
        path = str(InstancePaths.plan(instance_id, model_name))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, indent=2)
    
    def read_plan(self, instance_id: str, model_name: str = "default_model") -> Optional[dict]:
        """Read execution plan for an instance."""
        path = str(InstancePaths.plan(instance_id, model_name))
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    def write_execution(self, instance_id: str, execution_data: dict, model_name: str = "default_model"):
        """Write execution results for an instance."""
        path = str(InstancePaths.execution(instance_id, model_name))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(execution_data, f, indent=2)
    
    def read_execution(self, instance_id: str, model_name: str = "default_model") -> Optional[dict]:
        """Read execution results for an instance."""
        path = str(InstancePaths.execution(instance_id, model_name))
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
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
