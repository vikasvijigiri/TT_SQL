SELECT 
  ship_to_region,
  ROUND(AVG(fill_rate::bigint), 2) AS avg_fill_rate
FROM "acme-chatbot".otif
GROUP BY ship_to_region
ORDER BY avg_fill_rate DESC