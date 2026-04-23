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
        self, dataset_name: str, project_id: str = None
    ) -> dict[str, Any]:
        """
        Fetch schema for all tables in a dataset using a single optimized query to INFORMATION_SCHEMA.COLUMNS.
        """
        client = self.get_client()
        settings = get_settings()
        target_project = project_id or settings.GCP_PROJECT_ID or client.project

        # Resolve dataset and project reference
        if "." in dataset_name:
            # Handle project.dataset format
            parts = dataset_name.split(".")
            target_project = parts[0]
            target_dataset = parts[1]
        else:
            target_dataset = dataset_name

        Logger.log(
            f"[BQ] Fetching Batch Schema for `{target_project}.{target_dataset}` via INFORMATION_SCHEMA..."
        )

        # Single query to get all columns for all tables in the dataset
        query = f"""
        SELECT 
            table_name, 
            column_name, 
            data_type
        FROM 
            `{target_project}.{target_dataset}.INFORMATION_SCHEMA.COLUMNS`
        ORDER BY 
            table_name, ordinal_position
        """

        try:
            query_job = client.query(query)
            results = query_job.result()

            schema_info = {}
            for row in results:
                # Use fully qualified table names to ensure LLM generates executable SQL
                full_table_name = f"{target_project}.{target_dataset}.{row.table_name}"
                if full_table_name not in schema_info:
                    schema_info[full_table_name] = {"columns": []}

                schema_info[full_table_name]["columns"].append(
                    {
                        "column_name": row.column_name,
                        "type": row.data_type,
                        "description": "",
                        "pk": False,  # BQ doesn't have traditional PKs in INFORMATION_SCHEMA
                    }
                )

            Logger.log(
                f"[BQ] Schema Discovery Complete: Found {len(schema_info)} tables in `{target_dataset}`."
            )
            return schema_info
        except Exception as e:
            Logger.log(f"[BQ] Failed to fetch Batch Schema: {e}", level="ERROR")
            # Fallback to empty to allow pipeline to continue or fail gracefully
            return {}
