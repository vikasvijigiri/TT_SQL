SELECT 
  reason_for_cancellation,
  COUNT(*) AS cancellation_count
FROM "acme-chatbot".otif
WHERE cancellation_dt IS NOT NULL
  AND DATE_TRUNC('month', TO_DATE(reporting_date, 'YYYY-MM-DD')) = DATE_TRUNC('month', CURRENT_DATE)
GROUP BY reason_for_cancellation
ORDER BY cancellation_count DESC