WITH filtered_cases AS (
  SELECT c."IssueId__c" AS issue_id
  FROM "support_db"."Case" c
  JOIN "products_orders_db"."OrderItem" oi
    ON TRIM(c."OrderItemId__c", '# ') = TRIM(oi."Id", '# ')
  WHERE TRIM(oi."Product2Id", '# ') = '01tWt000006hV8LIAU'
    AND TRY_CAST(SUBSTR(c."CreatedDate", 1, 19) AS TIMESTAMP) >= (CAST('2023-01-16' AS TIMESTAMP) - INTERVAL '5 months')
    AND TRY_CAST(SUBSTR(c."CreatedDate", 1, 19) AS TIMESTAMP) < CAST('2023-01-16' AS TIMESTAMP)
    AND c."IssueId__c" IS NOT NULL
), issue_counts AS (
  SELECT issue_id, COUNT(*) AS cnt
  FROM filtered_cases
  GROUP BY issue_id
)
SELECT issue_id
FROM issue_counts
ORDER BY cnt DESC, issue_id ASC
LIMIT 1;