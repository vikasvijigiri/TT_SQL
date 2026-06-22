import duckdb, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_crmarenapro\query_dataset'
conn = duckdb.connect(f'{base}/sales_pipeline.duckdb', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/support.db' AS support_db (TYPE sqlite)")
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "CaseHistory__c" AS SELECT * FROM support_db."CaseHistory__c"')
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "Case" AS SELECT * FROM support_db."Case"')

# Check closed dates range
r = conn.execute('''
    SELECT MIN("ClosedDate"), MAX("ClosedDate"),
           MIN("CreatedDate"), MAX("CreatedDate")
    FROM "Case"
    WHERE "ClosedDate" IS NOT NULL
''').fetchone()
print(f"Closed range: {r[0]} to {r[1]}")
print(f"Created range: {r[2]} to {r[3]}")

# Test with 4 months from latest ClosedDate
r2 = conn.execute('''
    SELECT COUNT(DISTINCT "OwnerId") as owners, COUNT(*) as cases
    FROM "Case"
    WHERE "ClosedDate" IS NOT NULL
      AND TRY_CAST("ClosedDate" AS TIMESTAMP) >= TIMESTAMP '2023-08-02'
      AND TRY_CAST("ClosedDate" AS TIMESTAMP) <= TIMESTAMP '2023-12-02'
''').fetchone()
print(f"\nClosed in 4 months before 2023-12-02 (last date): {r2[1]} cases, {r2[0]} owners")

# Try with no date filter (all closed cases)
r3 = conn.execute('''
    WITH ac AS (
        SELECT "CaseId__c", COUNT(*) AS assign_cnt
        FROM "CaseHistory__c"
        WHERE "Field__c" = 'Owner Assignment'
        GROUP BY "CaseId__c"
    )
    SELECT c."OwnerId", COUNT(*) as cases,
           AVG(date_diff('second', TRY_CAST(c."CreatedDate" AS TIMESTAMP), TRY_CAST(c."ClosedDate" AS TIMESTAMP))) AS avg_handle_s
    FROM "Case" c
    JOIN ac ON REPLACE(c."Id", '#', '') = REPLACE(ac."CaseId__c", '#', '')
    WHERE ac.assign_cnt = 1
      AND c."ClosedDate" IS NOT NULL
    GROUP BY c."OwnerId"
    HAVING COUNT(*) > 1
    ORDER BY avg_handle_s ASC
    LIMIT 5
''').fetchdf()
print(f"\nAll closed non-transferred cases (no date filter):")
print(r3)

# Try 4 months ending at last ClosedDate
r4 = conn.execute('''
    WITH ac AS (
        SELECT "CaseId__c", COUNT(*) AS assign_cnt
        FROM "CaseHistory__c"
        WHERE "Field__c" = 'Owner Assignment'
        GROUP BY "CaseId__c"
    )
    SELECT c."OwnerId", COUNT(*) as cases,
           AVG(date_diff('second', TRY_CAST(c."CreatedDate" AS TIMESTAMP), TRY_CAST(c."ClosedDate" AS TIMESTAMP))) AS avg_handle_s
    FROM "Case" c
    JOIN ac ON REPLACE(c."Id", '#', '') = REPLACE(ac."CaseId__c", '#', '')
    WHERE ac.assign_cnt = 1
      AND c."ClosedDate" IS NOT NULL
      AND TRY_CAST(c."ClosedDate" AS TIMESTAMP) >= TIMESTAMP '2023-08-02'
    GROUP BY c."OwnerId"
    HAVING COUNT(*) > 1
    ORDER BY avg_handle_s ASC
    LIMIT 5
''').fetchdf()
print(f"\nClosed >= 2023-08-02 (4 months before DB max):")
print(r4)

conn.close()
