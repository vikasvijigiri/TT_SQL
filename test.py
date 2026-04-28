import sys
sys.path.append('src')
from core.sf_service import SnowflakeService

sf = SnowflakeService()
conn = sf.get_connection(database='PATENTS')
cursor = conn.cursor()
query = """
SELECT DISTINCT 
    REGEXP_REPLACE(f.path, '\\\\[[0-9]+\\\\]\\\\.?', '') AS key_name, 
    TYPEOF(f.value) AS key_type 
FROM PATENTS.PATENTS.PUBLICATIONS p, 
LATERAL FLATTEN(input => p."cpc", RECURSIVE => TRUE) f 
WHERE TYPEOF(f.value) NOT IN ('OBJECT', 'ARRAY') 
  AND f.path IS NOT NULL AND f.path != ''
LIMIT 100
"""
cursor.execute(query)
print('keys:', cursor.fetchall())
