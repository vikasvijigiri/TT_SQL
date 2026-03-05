SELECT 
  material_desc,
  ROUND(AVG(on_time_in_full_loss::bigint), 2) AS avg_otif,
  COUNT(*) AS total_orders
FROM "acme-chatbot".otif
GROUP BY material_desc
ORDER BY avg_otif