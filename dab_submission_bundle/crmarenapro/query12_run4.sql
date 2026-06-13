SELECT REPLACE(TRIM(o.OwnerId), '#', '') AS Id,
       AVG(DATEDIFF('day',
           TRY_CAST(o.CreatedDate AS TIMESTAMP)::DATE,
           TRY_CAST(c.CompanySignedDate AS DATE))) AS avg_turnaround_days
FROM Opportunity o
JOIN Contract c ON REPLACE(TRIM(o.ContractID__c), '#', '') = REPLACE(TRIM(c.Id), '#', '')
WHERE TRY_CAST(c.CompanySignedDate AS DATE) >= DATE '2023-04-01'
  AND TRY_CAST(c.CompanySignedDate AS DATE) < DATE '2023-05-01'
  AND o.ContractID__c IS NOT NULL AND TRIM(o.ContractID__c) != ''
GROUP BY REPLACE(TRIM(o.OwnerId), '#', '')
ORDER BY avg_turnaround_days ASC, REPLACE(TRIM(o.OwnerId), '#', '') ASC
LIMIT 1