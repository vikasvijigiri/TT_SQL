import json
import os
from core.sf_service import SnowflakeService

def inspect():
    svc = SnowflakeService()
    try:
        # Test f.value::TEXT (incorrect for objects) vs f.value:code::TEXT (correct)
        query = '''
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN f.value::TEXT LIKE 'A61%' THEN 1 END) as cast_match,
            COUNT(CASE WHEN f.value:code::TEXT LIKE 'A61%' THEN 1 END) as path_match
        FROM "PATENTS"."PATENTS"."PUBLICATIONS",
        LATERAL FLATTEN(input => "cpc") f
        LIMIT 100
        '''
        results = svc.execute_query(query)
        print("RESULTS:", json.dumps(results.rows, indent=2))
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    inspect()
