SELECT shippment_no, COUNT(*) AS delay_count
FROM "acme-chatbot".otif
WHERE on_time = 0 and shippment_no is not null
GROUP BY shippment_no
ORDER BY delay_count DESC
LIMIT 10