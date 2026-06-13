SELECT REPLACE(TRIM(c.OwnerId), '#', '') AS AgentId,
       AVG(DATEDIFF('minute', TRY_CAST(c.CreatedDate AS TIMESTAMP), TRY_CAST(c.ClosedDate AS TIMESTAMP))) AS avg_handle_minutes
FROM support_db.Case c
JOIN (
    SELECT REPLACE(TRIM(CaseId__c), '#', '') AS case_id
    FROM support_db.CaseHistory__c
    WHERE Field__c = 'Owner Assignment'
    GROUP BY REPLACE(TRIM(CaseId__c), '#', '')
    HAVING COUNT(*) = 1
) oa ON REPLACE(TRIM(c.Id), '#', '') = oa.case_id
WHERE TRY_CAST(c.CreatedDate AS TIMESTAMP) >= TIMESTAMP '2023-05-02 00:00:00'
  AND TRY_CAST(c.CreatedDate AS TIMESTAMP) <= TIMESTAMP '2023-09-02 23:59:59'
  AND c.ClosedDate IS NOT NULL
  AND REPLACE(TRIM(c.OwnerId), '#', '') IN (
      SELECT REPLACE(TRIM(OwnerId), '#', '')
      FROM support_db.Case
      WHERE TRY_CAST(CreatedDate AS TIMESTAMP) >= TIMESTAMP '2023-05-02 00:00:00'
        AND TRY_CAST(CreatedDate AS TIMESTAMP) <= TIMESTAMP '2023-09-02 23:59:59'
      GROUP BY REPLACE(TRIM(OwnerId), '#', '')
      HAVING COUNT(*) > 1
  )
GROUP BY REPLACE(TRIM(c.OwnerId), '#', '')
ORDER BY avg_handle_minutes ASC LIMIT 1