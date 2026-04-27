import os
from typing import Any

from google.cloud import bigquery
from google.oauth2 import service_account

from .config import get_settings
from .logger import Logger


class BigQueryService:
    """
    Service for BigQuery interactions.
    Optimized for batch metadata retrieval using INFORMATION_SCHEMA.
    """

    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset(cls):
        """Resets the BigQuery client and instance."""
        cls._client = None
        cls._instance = None
        Logger.log("BigQueryService state reset.", level="DEBUG")

    def get_client(self):
        if self._client is None:
            settings = get_settings()
            creds_path = settings.gcp_credentials_abs_path
            project_id = settings.GCP_PROJECT_ID

            if creds_path and os.path.exists(creds_path):
                Logger.log(
                    f"[BQ] Initializing client with credentials from: {creds_path}"
                )
                credentials = service_account.Credentials.from_service_account_file(
                    creds_path
                )
                self._client = bigquery.Client(
                    credentials=credentials,
                    project=project_id or credentials.project_id,
                )
            else:
                Logger.log(
                    f"[BQ] Credentials file NOT found at {creds_path}. Falling back to default credentials.",
                    level="WARN",
                )
                self._client = bigquery.Client(project=project_id)
            
            Logger.log(f"[BQ] Using Google Project ID: {self._client.project}")
        return self._client

    def get_dataset_schema(
        self, dataset_name: str, project_id: str = None, table_list: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Fetch schema for tables in a dataset (No INFORMATION_SCHEMA).
        Uses client.get_table() for ground truth metadata.
        """
        client = self.get_client()
        settings = get_settings()
        
        # Enforce Schema == Database (Dataset == Project) if possible, but allow overrides
        target_project = project_id or settings.GCP_PROJECT_ID or client.project
        target_dataset = dataset_name.split(".")[-1] # Ensure we just get the dataset part

        Logger.log(
            f"[BQ] Fetching Schema for `{target_project}.{target_dataset}` via get_table (No INFORMATION_SCHEMA)..."
        )

        schema_info = {}
        # If no table_list, list all tables first
        tables_to_inspect = []
        if table_list:
            tables_to_inspect = [t.split('.')[-1].replace('"', '') for t in table_list]
        else:
            try:
                tables = client.list_tables(f"{target_project}.{target_dataset}")
                tables_to_inspect = [table.table_id for table in tables]
            except Exception as e:
                Logger.log(f"[BQ] list_tables failed: {e}", level="ERROR")
                return {}

        for tname in tables_to_inspect:
            try:
                table_ref = client.get_table(f"{target_project}.{target_dataset}.{tname}")
                full_table_name = f"{target_project}.{target_dataset}.{tname}"
                
                schema_info[full_table_name] = {"columns": []}
                for field in table_ref.schema:
                    schema_info[full_table_name]["columns"].append(
                        {
                            "column_name": field.name,
                            "type": field.field_type,
                            "description": field.description or "",
                            "pk": False,
                        }
                    )
            except Exception as e:
                Logger.log(f"[BQ] Failed to get table {tname}: {e}", level="DEBUG")

        Logger.log(f"[BQ] Schema Discovery Complete: Found {len(schema_info)} tables.")
        return schema_info

    def get_table_names(self, dataset_name: str, project_id: str = None) -> list[str]:
        """Fetch qualified table names via client.list_tables() (No INFORMATION_SCHEMA)."""
        client = self.get_client()
        settings = get_settings()
        target_project = project_id or settings.GCP_PROJECT_ID or client.project
        target_dataset = dataset_name.split(".")[-1]
            
        try:
            tables = client.list_tables(f"{target_project}.{target_dataset}")
            qualified_tables = [f"{target_project}.{target_dataset}.{table.table_id}" for table in tables]
            return qualified_tables
        except Exception as e:
            Logger.log(f"[BQ] Failed to fetch table names via SDK: {e}", level="ERROR")
            return []
