SELECT product_description, SUM(batch) AS total_batch
FROM "acme-chatbot"."manufacturing-tracker"
where product_description is not null
GROUP BY product_description
ORDER BY total_batch DESC