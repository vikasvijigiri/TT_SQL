import psycopg2
from typing import Dict, Any, List
from app.repositories.config import settings
from app.services.utils.logger import Logger

class ExtractionService:
    def __init__(self):
        self.logger = Logger

    def get_db_connection(self):
        try:
            conn = psycopg2.connect(
                user=settings.RDS_USER,
                password=settings.RDS_PASSWORD,
                host=settings.RDS_HOST,
                port=settings.RDS_PORT,
                database=settings.RDS_DATABASE,
                connect_timeout=30
            )
            return conn
        except Exception as e:
            self.logger.log(f"Database Connection Error: {e}", level="ERROR")
            raise

    def extract_metadata(self, schema_name: str) -> Dict[str, Any]:
        """Extracts table names, columns types, and sample data from PostgreSQL."""
        self.logger.log(f"Extracting raw schema from: {schema_name}")
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_type = 'BASE TABLE';
            """, (schema_name,))
            tables = [r[0] for r in cur.fetchall()]
            
            metadata = {"schema": schema_name, "tables": {}}
            for table_name in tables:
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position;
                """, (schema_name, table_name))
                columns = cur.fetchall()
                
                col_meta = []
                for col_name, data_type in columns:
                    cur.execute(f'SELECT "{col_name}" FROM "{schema_name}"."{table_name}" WHERE "{col_name}" IS NOT NULL LIMIT 3;')
                    samples = [str(r[0]) for r in cur.fetchall()]
                    
                    col_meta.append({
                        "table_name": table_name,
                        "column_name": col_name,
                        "type": data_type,
                        "sample_values": samples
                    })
                
                metadata["tables"][table_name] = {"columns": col_meta}
            return metadata
        finally:
            cur.close()
            conn.close()

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Standalone Metadata Extraction Tool")
    parser.add_argument("--schema", type=str, default=settings.SCHEMA or "public", help="Database schema to extract")
    parser.add_argument("--output", type=str, help="Optional path to save JSON output")
    args = parser.parse_args()
    
    service = ExtractionService()
    metadata = service.extract_metadata(args.schema)
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
        print(f"Metadata saved to {args.output}")
    else:
        print(json.dumps(metadata, indent=2))
