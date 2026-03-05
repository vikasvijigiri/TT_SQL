SELECT fg_code, COUNT(DISTINCT component) AS components_count
FROM "acme-chatbot"."material-packing-tracker"
GROUP BY fg_code
ORDER BY components_count DESC