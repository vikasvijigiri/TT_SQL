import psycopg2
import os
from typing import List, Dict, Any

class SQLDiscoveryService:
    """
    Service to discover databases and schemas on a database server.
    """
    
    @staticmethod
    def discover_databases(config: Dict[str, Any]) -> List[str]:
        # ... (lines 10-31)
        try:
            conn = psycopg2.connect(
                host=config["host"],
                database="postgres", # System default
                user=config["user"],
                password=config["password"],
                port=config["port"],
                connect_timeout=5
            )
            cursor = conn.cursor()
            # Exclude templates and system databases
            query = "SELECT datname FROM pg_database WHERE datistemplate = false AND datname NOT IN ('postgres', 'rdsadmin');"
            cursor.execute(query)
            databases = [row[0] for row in cursor.fetchall()]
            conn.close()
            return databases
        except Exception as e:
            raise Exception(f"Failed to discover databases: {str(e)}")

    @staticmethod
    def discover_schemas(config: Dict[str, Any], database: str) -> List[str]:
        # ... (lines 35-63)
        try:
            conn = psycopg2.connect(
                host=config["host"],
                database=database,
                user=config["user"],
                password=config["password"],
                port=config["port"],
                connect_timeout=5
            )
            cursor = conn.cursor()
            # Exclude system schemas
            query = """
                SELECT nspname 
                FROM pg_namespace 
                WHERE nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast') 
                AND nspname NOT LIKE 'pg_temp_%' 
                AND nspname NOT LIKE 'pg_toast_temp_%'
                ORDER BY nspname;
            """
            cursor.execute(query)
            schemas = [row[0] for row in cursor.fetchall()]
            conn.close()
            return schemas
        except Exception as e:
            raise Exception(f"Failed to discover schemas in '{database}': {str(e)}")

    @staticmethod
    def discover_sqlite_files(directory_path: str) -> List[str]:
        """
        List all .db or .sqlite files in a local directory.
        """
        if not os.path.exists(directory_path):
            raise Exception(f"Path does not exist: {directory_path}")
        if not os.path.isdir(directory_path):
            raise Exception(f"Path is not a directory: {directory_path}")
            
        try:
            files = []
            valid_extensions = ('.db', '.sqlite', '.sqlite3', '.duckdb')
            for f in os.listdir(directory_path):
                if f.lower().endswith(valid_extensions):
                    files.append(f)
            return sorted(files)
        except Exception as e:
            raise Exception(f"Failed to scan directory: {str(e)}")
