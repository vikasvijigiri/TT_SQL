WITH single_assign_cases AS (
    SELECT REPLACE(TRIM("CaseId__c"), '#', '') AS case_id
    FROM "CaseHistory__c"
    WHERE LOWER(TRIM("Field__c")) LIKE '%owner assignment%'
    GROUP BY REPLACE(TRIM("CaseId__c"), '#', '')
    HAVING COUNT(*) = 1
),
filtered_cases AS (
    SELECT REPLACE(TRIM(c."Id"), '#', '') AS case_id,
           REPLACE(TRIM(c."OwnerId"), '#', '') AS owner_id,
           TRY_CAST(REPLACE(SUBSTR(c."CreatedDate", 1, 19), 'T', ' ') AS TIMESTAMP) AS created_ts,
           TRY_CAST(REPLACE(SUBSTR(c."ClosedDate", 1, 19), 'T', ' ') AS TIMESTAMP) AS closed_ts
    FROM "Case" c
    JOIN single_assign_cases sac ON sac.case_id = REPLACE(TRIM(c."Id"), '#', '')
    WHERE c."ClosedDate" IS NOT NULL
      AND TRY_CAST(REPLACE(SUBSTR(c."CreatedDate", 1, 19), 'T', ' ') AS TIMESTAMP) >= TIMESTAMP '2023-05-02 00:00:00'
      AND TRY_CAST(REPLACE(SUBSTR(c."CreatedDate", 1, 19), 'T', ' ') AS TIMESTAMP) <= TIMESTAMP '2023-09-02 23:59:59'
),
agent_metrics AS (
    SELECT owner_id,
           AVG(EXTRACT(EPOCH FROM (closed_ts - created_ts))) AS avg_handle_seconds,
           COUNT(*) AS case_cnt
    FROM filtered_cases
    GROUP BY owner_id
    HAVING COUNT(*) > 1
)
SELECT owner_id AS Id
FROM agent_metrics
ORDER BY avg_handle_seconds ASC
LIMIT 1;