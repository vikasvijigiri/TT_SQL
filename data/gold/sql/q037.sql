SELECT component, component_name,
       SUM(total_stock) - SUM(total_required_qty) AS stock_difference
FROM "acme-chatbot"."material-packing-tracker"
GROUP BY component, component_name
ORDER BY stock_difference DESC