WITH parsed_cases AS (
    SELECT c."IssueId__c",
           TRY_STRPTIME(SUBSTR(c."CreatedDate",1,19), '%Y-%m-%dT%H:%M:%S') AS created_ts,
           REPLACE(TRIM(c."OrderItemId__c"), '#', '') AS case_oi_id
    FROM "Case" c
), filtered_cases AS (
    SELECT pc."IssueId__c"
    FROM parsed_cases pc
    JOIN "OrderItem" oi
      ON pc.case_oi_id = REPLACE(TRIM(oi."Id"), '#', '')
    WHERE REPLACE(TRIM(oi."Product2Id"), '#', '') = '01tWt000006hV8LIAU'
      AND pc.created_ts >= (CAST('2023-01-16' AS TIMESTAMP) - INTERVAL '5 months')
      AND pc.created_ts < CAST('2023-01-16' AS TIMESTAMP)
      AND pc."IssueId__c" IS NOT NULL
), issue_counts AS (
    SELECT "IssueId__c" AS issue_id, COUNT(*) AS cnt
    FROM filtered_cases
    GROUP BY "IssueId__c"
)
SELECT issue_id
FROM issue_counts
ORDER BY cnt DESC, issue_id ASC
LIMIT 1;