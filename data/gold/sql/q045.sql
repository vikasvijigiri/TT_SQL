SELECT component, (SUM(total_required_qty) - SUM(total_stock)) AS shortage
FROM "acme-chatbot"."material-packing-tracker"
GROUP BY component
ORDER BY shortage DESC
LIMIT 10