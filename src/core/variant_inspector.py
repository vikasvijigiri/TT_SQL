import json
import os
from pathlib import Path
from typing import Any, Dict, List
from core.sf_service import SnowflakeService
from core.logger import Logger
from core.paths import METADATA_DIR
from core.utils import quote_identifier

class VariantInspector:
    """
    Module for inspecting Snowflake VARIANT (JSON) columns with strict quoting rules.
    Provides caching and safe identifier handling.
    """
    
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.cache_dir = METADATA_DIR / "variant_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_dir / f"{db_name}_variants.json"
        self._cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                Logger.log(f"Failed to load variant cache: {e}", level="WARN")
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            Logger.log(f"Failed to save variant cache: {e}", level="WARN")

    # quote_identifier is now imported from utils

    def build_fqn(self, database: str, schema: str, table: str) -> str:
        """Build fully qualified table name with proper quoting."""
        return ".".join([
            quote_identifier(database),
            quote_identifier(schema),
            quote_identifier(table)
        ])

    def inspect_column(self, table_name: str, column_name: str, sample_size: int = 100) -> Dict[str, Any]:
        """
        Extract JSON keys from a VARIANT column in Snowflake with strict quoting.
        """
        cache_key = f"{table_name}.{column_name}"
        if cache_key in self._cache:
            Logger.log(f"Using cached variant structure for {cache_key}")
            return self._cache[cache_key]

        Logger.log(f"Inspecting VARIANT structure for {cache_key}...")
        
        sf = SnowflakeService()
        conn = sf.get_connection(database=self.db_name)
        if not conn:
            return {"column": cache_key, "keys": {}, "status": "unknown"}

        # Resolving exact casing from Snowflake
        try:
            r_db = sf.get_real_database_name(conn, self.db_name)
            r_sch = sf.get_real_schema_name(conn, r_db, self.db_name)
            
            # Extract base table name if FQN was passed
            base_tab = table_name.split(".")[-1].replace('"', '').replace('`', '').strip()
            r_tab = sf.get_real_table_name(conn, r_db, r_sch, base_tab)
            r_col = sf.get_real_column_name(conn, r_db, r_sch, r_tab, column_name)
            
            fqn = self.build_fqn(r_db, r_sch, r_tab)
            col = quote_identifier(r_col)
        except Exception as e:
            Logger.log(f"Resolution failed for variant column {table_name}.{column_name}: {e}", level="ERROR")
            return {"column": cache_key, "keys": {}, "status": "unknown"}

        query = f"""
        WITH base AS (
            SELECT {col} AS variant_col
            FROM {fqn}
            WHERE {col} IS NOT NULL
            LIMIT {sample_size}
        ),
        level1 AS (
            SELECT f.value AS lvl1_value
            FROM base,
            LATERAL FLATTEN(
                input => CASE 
                    WHEN TYPEOF(variant_col) = 'ARRAY' THEN variant_col
                    ELSE ARRAY_CONSTRUCT(variant_col)
                END
            ) f
        )
        SELECT DISTINCT 
            k.value::STRING AS key_name,
            TYPEOF(lvl1_value[k.value]) AS key_type
        FROM level1,
        LATERAL FLATTEN(input => OBJECT_KEYS(lvl1_value)) k
        WHERE TYPEOF(lvl1_value) = 'OBJECT'
        """
        
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Extract keys and their types
            keys = {row[0]: row[1] for row in rows if row[0]}
            
            status = "known" if keys else "unknown"
            result = {
                "column": cache_key,
                "keys": keys,
                "status": status
            }
            
            self._cache[cache_key] = result
            self._save_cache()
            return result
            
        except Exception as e:
            Logger.log(f"[ERROR] Variant inspection failed for {table_name}.{column_name}: {e}", level="ERROR")
            return {"column": cache_key, "keys": {}, "status": "unknown"}
        finally:
            if cursor:
                cursor.close()

    def get_all_variant_metadata(self) -> Dict[str, Any]:
        return self._cache
