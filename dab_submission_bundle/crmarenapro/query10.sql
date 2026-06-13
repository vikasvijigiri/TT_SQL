WITH cleaned_cases AS (
  SELECT REPLACE(TRIM(c."Id"), '#', '') AS case_id,
         REPLACE(TRIM(c."OwnerId"), '#', '') AS owner_id,
         TRY_CAST(REPLACE(SUBSTR(c."CreatedDate",1,19), 'T', ' ') AS TIMESTAMP) AS created_ts,
         TRY_CAST(REPLACE(SUBSTR(c."ClosedDate",1,19), 'T', ' ') AS TIMESTAMP) AS closed_ts
  FROM "support_db"."Case" c
  WHERE c."ClosedDate" IS NOT NULL
    AND TRY_CAST(REPLACE(SUBSTR(c."CreatedDate",1,19), 'T', ' ') AS TIMESTAMP) >= TIMESTAMP '2023-05-02 00:00:00'
    AND TRY_CAST(REPLACE(SUBSTR(c."CreatedDate",1,19), 'T', ' ') AS TIMESTAMP) <= TIMESTAMP '2023-09-02 23:59:59'
),
single_assign_cases AS (
  SELECT cc.case_id,
         cc.owner_id,
         epoch(cc.closed_ts) - epoch(cc.created_ts) AS handle_seconds
  FROM cleaned_cases cc
  JOIN (
    SELECT REPLACE(TRIM(ch."CaseId__c"), '#', '') AS case_id,
           COUNT(*) AS assign_cnt
    FROM "support_db"."CaseHistory__c" ch
    WHERE LOWER(TRIM(ch."Field__c")) = 'owner assignment'
    GROUP BY REPLACE(TRIM(ch."CaseId__c"), '#', '')
  ) ac ON cc.case_id = ac.case_id
  WHERE ac.assign_cnt = 1
)
SELECT owner_id AS "Id"
FROM (
  SELECT owner_id,
         AVG(handle_seconds) AS avg_handle_seconds,
         COUNT(*) AS case_cnt
  FROM single_assign_cases
  GROUP BY owner_id
  HAVING COUNT(*) > 1
) agg
ORDER BY avg_handle_seconds ASC
LIMIT 1;