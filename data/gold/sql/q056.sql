SELECT cust_name, AVG(open_deliv_qty) AS avg_open_delivery_qty
FROM "acme-chatbot".otif
GROUP BY cust_name
ORDER BY avg_open_delivery_qty DESC
LIMIT 10