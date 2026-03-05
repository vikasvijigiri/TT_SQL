SELECT material, material_desc, COUNT(*) AS delay_count
FROM "acme-chatbot".otif
WHERE on_time = 0
GROUP BY material, material_desc
ORDER BY delay_count DESC
LIMIT 10