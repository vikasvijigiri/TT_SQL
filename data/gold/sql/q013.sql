SELECT material, prod_desc, net_stock
FROM "acme-chatbot".doh
WHERE net_stock <= 0
ORDER BY net_stock