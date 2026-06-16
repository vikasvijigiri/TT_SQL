WITH
    period AS (
        SELECT
            DATE_TRUNC('quarter', CAST('2023-04-10' AS DATE)) - INTERVAL '1 year' AS start_date,
            DATE_TRUNC('quarter', CAST('2023-04-10' AS DATE)) AS end_date
    ),
    case_counts AS (
        SELECT
            TRIM(BOTH '#' FROM TRIM("OwnerId")) AS agent_id,
            COUNT(*) AS case_cnt
        FROM "support_db"."Case"
        WHERE TRY_CAST("CreatedDate" AS TIMESTAMP) >= (SELECT start_date FROM period)
          AND TRY_CAST("CreatedDate" AS TIMESTAMP) <  (SELECT end_date FROM period)
        GROUP BY agent_id
    ),
    transfer_counts AS (
        SELECT
            TRIM(BOTH '#' FROM TRIM("OldValue__c")) AS agent_id,
            COUNT(*) AS transfer_cnt
        FROM "support_db"."CaseHistory__c"
        WHERE "Field__c" = 'Owner Assignment'
          AND TRY_CAST("CreatedDate" AS TIMESTAMP) >= (SELECT start_date FROM period)
          AND TRY_CAST("CreatedDate" AS TIMESTAMP) <  (SELECT end_date FROM period)
        GROUP BY agent_id
    )
SELECT cc.agent_id AS Id
FROM case_counts cc
LEFT JOIN transfer_counts tc ON cc.agent_id = tc.agent_id
WHERE cc.case_cnt > 0
ORDER BY COALESCE(tc.transfer_cnt, 0) ASC, cc.agent_id
LIMIT 1;