SELECT material, prod_desc, availablity, doh
FROM "acme-chatbot".doh
WHERE critical_sku = 'Yes' AND availablity < 50
ORDER BY availablity