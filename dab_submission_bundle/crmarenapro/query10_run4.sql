WITH assign_counts AS (
    SELECT REPLACE(TRIM("CaseId__c"), '#', '') AS case_id,
           COUNT(*) AS assign_cnt
    FROM "support_db"."CaseHistory__c"
    WHERE LOWER(TRIM("Field__c")) LIKE '%owner assignment%'
    GROUP BY REPLACE(TRIM("CaseId__c"), '#', '')
),
filtered_cases AS (
    SELECT REPLACE(TRIM(c."Id"), '#', '') AS case_id,
           REPLACE(TRIM(c."OwnerId"), '#', '') AS owner_id,
           TRY_CAST(REPLACE(SUBSTR(c."CreatedDate", 1, 19), 'T', ' ') AS TIMESTAMP) AS created_ts,
           TRY_CAST(REPLACE(SUBSTR(c."ClosedDate", 1, 19), 'T', ' ') AS TIMESTAMP) AS closed_ts
    FROM "support_db"."Case" c
    JOIN assign_counts ac ON ac.case_id = REPLACE(TRIM(c."Id"), '#', '')
    WHERE ac.assign_cnt = 1
      AND c."ClosedDate" IS NOT NULL
      AND TRY_CAST(REPLACE(SUBSTR(c."CreatedDate", 1, 19), 'T', ' ') AS TIMESTAMP) >= TIMESTAMP '2023-05-02 00:00:00'
      AND TRY_CAST(REPLACE(SUBSTR(c."CreatedDate", 1, 19), 'T', ' ') AS TIMESTAMP) <= TIMESTAMP '2023-09-02 23:59:59'
),
owner_stats AS (
    SELECT owner_id,
           AVG(EXTRACT(EPOCH FROM (closed_ts - created_ts))) AS avg_handle_seconds,
           COUNT(*) AS case_cnt
    FROM filtered_cases
    GROUP BY owner_id
    HAVING COUNT(*) > 1
)
SELECT owner_id AS Id
FROM owner_stats
ORDER BY avg_handle_seconds ASC
LIMIT 1;