import psycopg2
import sqlite3
from typing import Dict, Any, List
from app.repositories.connectors.sql_repo import DBRepository
from app.services.utils.logger import Logger

class ExtractionService:
    def __init__(self):
        self.logger = Logger

    def extract_metadata(self, schema_name: str, user_slug: str = None) -> Dict[str, Any]:
        """
        Extracts table names, columns types, and sample data.
        Supports both PostgreSQL and SQLite.
        """
        active = DBRepository._get_active_connection(user_slug=user_slug)
        db_type = active.get("db_type", "postgres").lower()
        
        self.logger.log(f"Extracting raw schema for user {user_slug} (Type: {db_type})")
        
        if db_type == "sqlite":
            return self._extract_sqlite(active.get("sqlite_path"), user_slug)
        else:
            return self._extract_postgres(schema_name, active, user_slug)

    def _extract_postgres(self, schema_name: str, active: dict, user_slug: str) -> Dict[str, Any]:
        self.logger.log(f"Extracting Postgres schema: {schema_name}")
        
        # Use DBRepository to execute queries instead of raw psycopg2 for consistency
        metadata = {"schema": schema_name, "tables": {}}
        
        # Get Tables
        table_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_type = 'BASE TABLE';
        """
        tables_res = DBRepository.execute_query(table_query, params=(schema_name,), user_slug=user_slug)
        tables = [r[0] for r in tables_res.rows]
        
        for table_name in tables:
            # Get Columns
            col_query = """
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position;
            """
            cols_res = DBRepository.execute_query(col_query, params=(schema_name, table_name), user_slug=user_slug)
            
            col_meta = []
            for col_name, data_type in cols_res.rows:
                # Get Sample Values (limit 3)
                sample_query = f'SELECT "{col_name}" FROM "{schema_name}"."{table_name}" WHERE "{col_name}" IS NOT NULL LIMIT 3;'
                sample_res = DBRepository.execute_query(sample_query, user_slug=user_slug)
                samples = [str(r[0]) for r in sample_res.rows]
                
                col_meta.append({
                    "table_name": table_name,
                    "column_name": col_name,
                    "type": data_type,
                    "sample_values": samples
                })
            
            metadata["tables"][table_name] = {"columns": col_meta}
        return metadata

    def _extract_sqlite(self, db_path: str, user_slug: str) -> Dict[str, Any]:
        self.logger.log(f"Extracting SQLite schema from: {db_path}")
        metadata = {"schema": "main", "tables": {}}
        
        # Get Tables
        tables_res = DBRepository.execute_query("SELECT name FROM sqlite_master WHERE type='table';", user_slug=user_slug)
        tables = [r[0] for r in tables_res.rows if not r[0].startswith('sqlite_')]
        
        for table_name in tables:
            # Get Columns via PRAGMA
            cols_res = DBRepository.execute_query(f"PRAGMA table_info({table_name});", user_slug=user_slug)
            
            col_meta = []
            for r in cols_res.rows:
                col_name = r[1]
                data_type = r[2]
                
                # Get Sample Values
                sample_query = f'SELECT "{col_name}" FROM "{table_name}" WHERE "{col_name}" IS NOT NULL LIMIT 3;'
                sample_res = DBRepository.execute_query(sample_query, user_slug=user_slug)
                samples = [str(r[0]) for r in sample_res.rows]
                
                col_meta.append({
                    "table_name": table_name,
                    "column_name": col_name,
                    "type": data_type,
                    "sample_values": samples
                })
            
            metadata["tables"][table_name] = {"columns": col_meta}
        return metadata

if __name__ == "__main__":
    # Internal CLI test usage
    import json
    service = ExtractionService()
    # Note: CLI testing needs ACTIVE_PROJECT_ID in env or similar
    print("ExtractionService loaded. Use within app context for DBRepository support.")
