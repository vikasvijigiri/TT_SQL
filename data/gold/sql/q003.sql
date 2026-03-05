SELECT 
  material,
  material_desc,
  SUM(order_qty) AS total_order_qty,
  COUNT(*) FILTER (WHERE on_time = 0) AS otif_failures
FROM "acme-chatbot".otif
GROUP BY material, material_desc
ORDER BY otif_failures DESC
LIMIT 10