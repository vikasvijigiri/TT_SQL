import duckdb, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_crmarenapro\query_dataset'
conn = duckdb.connect(f'{base}/sales_pipeline.duckdb', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/support.db' AS support_db (TYPE sqlite)")

# Create temp table like the executor does
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "CaseHistory__c" AS SELECT * FROM support_db."CaseHistory__c"')
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "Case" AS SELECT * FROM support_db."Case"')

print("=== CaseHistory__c sample ===")
r = conn.execute('SELECT "Field__c", COUNT(*) FROM "CaseHistory__c" GROUP BY "Field__c"').fetchdf()
print(r)

print("\n=== Case count ===")
r = conn.execute('SELECT COUNT(*) FROM "Case"').fetchone()
print(f"Cases: {r[0]}")

print("\n=== Date range check ===")
r = conn.execute('''
    SELECT MIN("CreatedDate"), MAX("CreatedDate"), COUNT(*)
    FROM "Case"
    WHERE "ClosedDate" IS NOT NULL
''').fetchone()
print(f"Closed cases date range: {r[0]} to {r[1]} ({r[2]} total)")

r2 = conn.execute('''
    SELECT COUNT(*) FROM "Case"
    WHERE "ClosedDate" IS NOT NULL
      AND TRY_CAST("CreatedDate" AS TIMESTAMP) >= TIMESTAMP '2023-05-02'
      AND TRY_CAST("CreatedDate" AS TIMESTAMP) <= TIMESTAMP '2023-09-02'
''').fetchone()
print(f"Cases in 2023-05-02 to 2023-09-02: {r2[0]}")

# Test full CRM q10 SQL
print("\n=== Full CRM q10 SQL ===")
sql = '''
WITH assign_counts AS (
  SELECT "CaseId__c", COUNT(*) AS assign_cnt
  FROM "CaseHistory__c"
  WHERE "Field__c" = 'Owner Assignment'
  GROUP BY "CaseId__c"
),
filtered_cases AS (
  SELECT c."OwnerId", c."CreatedDate", c."ClosedDate"
  FROM "Case" c
  JOIN assign_counts ac ON c."Id" = ac."CaseId__c"
  WHERE ac.assign_cnt = 1
    AND c."ClosedDate" IS NOT NULL
    AND TRY_CAST(c."CreatedDate" AS TIMESTAMP) >= TIMESTAMP '2023-05-02 00:00:00'
    AND TRY_CAST(c."CreatedDate" AS TIMESTAMP) <= TIMESTAMP '2023-09-02 23:59:59'
)
SELECT "OwnerId",
       AVG(date_diff('second', TRY_CAST("CreatedDate" AS TIMESTAMP), TRY_CAST("ClosedDate" AS TIMESTAMP))) AS avg_handle_seconds,
       COUNT(*) AS case_cnt
FROM filtered_cases
GROUP BY "OwnerId"
HAVING COUNT(*) > 1
ORDER BY avg_handle_seconds ASC
LIMIT 5
'''
try:
    r = conn.execute(sql).fetchdf()
    print(r)
except Exception as e:
    print(f"Error: {e}")

# Check Case.Id vs CaseHistory.CaseId__c join
print("\n=== Join check ===")
r = conn.execute('''
    SELECT COUNT(*) FROM "Case" c
    JOIN "CaseHistory__c" ch ON c."Id" = ch."CaseId__c"
    WHERE ch."Field__c" = 'Owner Assignment'
''').fetchone()
print(f"Cases with Owner Assignment in history: {r[0]}")

# Check if Id has # prefix
r = conn.execute('SELECT "Id", LEFT("Id", 3) AS prefix FROM "Case" LIMIT 3').fetchdf()
print(f"\nCase.Id samples: {r}")

r2 = conn.execute('SELECT "CaseId__c", LEFT("CaseId__c", 3) AS prefix FROM "CaseHistory__c" LIMIT 3').fetchdf()
print(f"\nCaseHistory.CaseId__c samples: {r2}")

conn.close()
