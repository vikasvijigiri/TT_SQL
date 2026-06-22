import duckdb, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_crmarenapro\query_dataset'
conn = duckdb.connect(f'{base}/sales_pipeline.duckdb', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/support.db' AS support_db (TYPE sqlite)")
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "CaseHistory__c" AS SELECT * FROM support_db."CaseHistory__c"')
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "Case" AS SELECT * FROM support_db."Case"')

EXPECTED = '005Wt000003NDqDIAW'

# Check: is the expected OwnerId in the data?
r = conn.execute(f'''
    SELECT "Id", "OwnerId", "CreatedDate", "ClosedDate"
    FROM "Case"
    WHERE "OwnerId" = '{EXPECTED}' OR REPLACE("OwnerId", '#', '') = '{EXPECTED}'
''').fetchdf()
print(f"Cases with expected OwnerId: {len(r)}")
print(r)

# What date range are they in?
if len(r) > 0:
    print("\nCreated dates:", r['CreatedDate'].tolist())
    print("Closed dates:", r['ClosedDate'].tolist())

# Try broader date range approaches
print("\n=== Try 4 months relative to most recent CLOSED date ===")
max_date = conn.execute('SELECT MAX(TRY_CAST("ClosedDate" AS TIMESTAMP)) FROM "Case"').fetchone()[0]
print(f"Max ClosedDate: {max_date}")

r2 = conn.execute('''
    WITH ac AS (
        SELECT REPLACE("CaseId__c", '#', '') AS case_id, COUNT(*) AS assign_cnt
        FROM "CaseHistory__c"
        WHERE "Field__c" = 'Owner Assignment'
        GROUP BY REPLACE("CaseId__c", '#', '')
    )
    SELECT REPLACE(c."OwnerId", '#', '') AS owner_id, COUNT(*) as cases,
           AVG(date_diff('second', TRY_CAST(c."CreatedDate" AS TIMESTAMP), TRY_CAST(c."ClosedDate" AS TIMESTAMP))) AS avg_handle_s
    FROM "Case" c
    JOIN ac ON REPLACE(c."Id", '#', '') = ac.case_id
    WHERE ac.assign_cnt = 1
      AND c."ClosedDate" IS NOT NULL
      AND TRY_CAST(c."ClosedDate" AS TIMESTAMP) >= (SELECT MAX(TRY_CAST("ClosedDate" AS TIMESTAMP)) FROM "Case") - INTERVAL '4 months'
    GROUP BY REPLACE(c."OwnerId", '#', '')
    HAVING COUNT(*) > 1
    ORDER BY avg_handle_s ASC
    LIMIT 5
''').fetchdf()
print("4 months before max ClosedDate:")
print(r2)

# Try with CreatedDate instead
r3 = conn.execute('''
    WITH ac AS (
        SELECT REPLACE("CaseId__c", '#', '') AS case_id, COUNT(*) AS assign_cnt
        FROM "CaseHistory__c"
        WHERE "Field__c" = 'Owner Assignment'
        GROUP BY REPLACE("CaseId__c", '#', '')
    )
    SELECT REPLACE(c."OwnerId", '#', '') AS owner_id, COUNT(*) as cases,
           AVG(date_diff('second', TRY_CAST(c."CreatedDate" AS TIMESTAMP), TRY_CAST(c."ClosedDate" AS TIMESTAMP))) AS avg_handle_s
    FROM "Case" c
    JOIN ac ON REPLACE(c."Id", '#', '') = ac.case_id
    WHERE ac.assign_cnt = 1
      AND c."ClosedDate" IS NOT NULL
      AND TRY_CAST(c."CreatedDate" AS TIMESTAMP) >= (SELECT MAX(TRY_CAST("CreatedDate" AS TIMESTAMP)) FROM "Case") - INTERVAL '4 months'
    GROUP BY REPLACE(c."OwnerId", '#', '')
    HAVING COUNT(*) > 1
    ORDER BY avg_handle_s ASC
    LIMIT 5
''').fetchdf()
print("\n4 months before max CreatedDate:")
print(r3)

conn.close()
