SELECT prod_family, ROUND(AVG(doh::bigint), 2) AS avg_doh
FROM "acme-chatbot"."batch-and-packing-tracker"
GROUP BY prod_family
ORDER BY avg_doh DESC