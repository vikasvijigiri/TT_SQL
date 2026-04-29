import sys
sys.path.append('src')
from core.semantic_fixer import apply_semantic_fixes, get_primary_entity_from_schema

schema_metadata = {
    'PATENTS.PATENTS.DISCLOSURES_13': {
        "columns": [
            {"column_name": "id"}
        ]
    }
}

sql = """
SELECT d.disclosure_event:"type"::STRING, COUNT(*) 
FROM DISCLOSURES_13 d 
GROUP BY 1
"""

plan = {}
dialect = "snowflake"

print("PRIMARY ENTITY:", get_primary_entity_from_schema(schema_metadata))

fixed_sql = apply_semantic_fixes(plan, sql, dialect, schema_metadata)
print("FIXED SQL:")
print(fixed_sql)
