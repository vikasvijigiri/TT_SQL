import duckdb, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_crmarenapro\query_dataset'
conn = duckdb.connect(f'{base}/sales_pipeline.duckdb', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/support.db' AS support_db (TYPE sqlite)")
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "CaseHistory__c" AS SELECT * FROM support_db."CaseHistory__c"')
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "Case" AS SELECT * FROM support_db."Case"')

EXPECTED = '005Wt000003NDqDIAW'

# Try: count all cases (including open) but only handle_time for closed
# "more than one case" = 2+ cases of ANY status
# "handle time" = average handle time for closed cases only
print("=== Approach 1: count all cases, handle time for closed only ===")
r = conn.execute('''
    WITH ac AS (
        SELECT REPLACE("CaseId__c", '#', '') AS case_id, COUNT(*) AS assign_cnt
        FROM "CaseHistory__c"
        WHERE "Field__c" = 'Owner Assignment'
        GROUP BY REPLACE("CaseId__c", '#', '')
    ),
    dated AS (
        SELECT REPLACE(c."OwnerId", '#', '') AS owner_id,
               REPLACE(c."Id", '#', '') AS case_id,
               c."CreatedDate", c."ClosedDate"
        FROM "Case" c
        JOIN ac ON REPLACE(c."Id", '#', '') = ac.case_id
        WHERE ac.assign_cnt = 1
          AND TRY_CAST(c."CreatedDate" AS TIMESTAMP) >= TIMESTAMP '2023-05-02'
          AND TRY_CAST(c."CreatedDate" AS TIMESTAMP) <= TIMESTAMP '2023-09-02'
    )
    SELECT owner_id,
           COUNT(*) as total_cases,
           COUNT("ClosedDate") as closed_cases,
           AVG(CASE WHEN "ClosedDate" IS NOT NULL
               THEN date_diff('second', TRY_CAST("CreatedDate" AS TIMESTAMP), TRY_CAST("ClosedDate" AS TIMESTAMP))
               END) AS avg_handle_s
    FROM dated
    GROUP BY owner_id
    HAVING COUNT(*) > 1
    ORDER BY avg_handle_s ASC NULLS LAST
    LIMIT 5
''').fetchdf()
print(r)
print(f"Expected in results: {EXPECTED in r.get('owner_id', {}).values}")

# Try without # normalization on OwnerId
print("\n=== Approach 2: no # normalization on OwnerId ===")
r2 = conn.execute('''
    WITH ac AS (
        SELECT REPLACE("CaseId__c", '#', '') AS case_id, COUNT(*) AS assign_cnt
        FROM "CaseHistory__c"
        WHERE "Field__c" = 'Owner Assignment'
        GROUP BY REPLACE("CaseId__c", '#', '')
    )
    SELECT c."OwnerId",
           COUNT(*) as total_cases,
           AVG(CASE WHEN c."ClosedDate" IS NOT NULL
               THEN date_diff('second', TRY_CAST(c."CreatedDate" AS TIMESTAMP), TRY_CAST(c."ClosedDate" AS TIMESTAMP))
               END) AS avg_handle_s
    FROM "Case" c
    JOIN ac ON REPLACE(c."Id", '#', '') = ac.case_id
    WHERE ac.assign_cnt = 1
      AND TRY_CAST(c."CreatedDate" AS TIMESTAMP) >= TIMESTAMP '2023-05-02'
      AND TRY_CAST(c."CreatedDate" AS TIMESTAMP) <= TIMESTAMP '2023-09-02'
    GROUP BY c."OwnerId"
    HAVING COUNT(*) > 1
    ORDER BY avg_handle_s ASC NULLS LAST
    LIMIT 5
''').fetchdf()
print(r2)
print(f"Expected in results: {EXPECTED in r2.get('OwnerId', {}).values}")

conn.close()
