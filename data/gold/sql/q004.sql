SELECT 
  TO_DATE(reporting_date, 'YYYY-MM-DD') AS report_day,
  ROUND(AVG(on_time_in_full_loss::bigint), 2) AS daily_otif_score
FROM "acme-chatbot".otif
WHERE TO_DATE(reporting_date, 'YYYY-MM-DD') >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY report_day
ORDER BY report_day