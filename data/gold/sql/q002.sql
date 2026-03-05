SELECT 
  cust_name,
  ROUND(AVG(on_time_in_full_loss::bigint), 2) AS otif_score
FROM "acme-chatbot".otif
WHERE DATE_TRUNC('month', TO_DATE(reporting_date, 'YYYY-MM-DD')) = DATE_TRUNC('month', CURRENT_DATE)
GROUP BY cust_name
ORDER BY otif_score ASC
LIMIT 10