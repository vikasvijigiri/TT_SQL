SELECT 
  carrier,
  ROUND(AVG(on_time_in_full_loss::bigint), 2) AS avg_otif
FROM "acme-chatbot".otif
GROUP BY carrier
HAVING AVG(on_time_in_full_loss) < 0.9
ORDER BY avg_otif