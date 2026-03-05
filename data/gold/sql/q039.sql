SELECT shortage_flag,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM "acme-chatbot"."material-packing-tracker"), 2) AS percentage
FROM "acme-chatbot"."material-packing-tracker"
GROUP BY shortage_flag