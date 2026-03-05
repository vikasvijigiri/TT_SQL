SELECT prod_family, COUNT(*) AS batch_count
FROM "acme-chatbot"."batch-and-packing-tracker"
GROUP BY prod_family
ORDER BY batch_count DESC