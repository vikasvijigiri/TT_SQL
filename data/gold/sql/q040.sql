SELECT COUNT(*) AS count_components
FROM "acme-chatbot"."material-packing-tracker"
WHERE total_required_qty > (SELECT AVG(total_required_qty) FROM "acme-chatbot"."material-packing-tracker")
  AND total_stock > (SELECT AVG(total_stock) FROM "acme-chatbot"."material-packing-tracker")