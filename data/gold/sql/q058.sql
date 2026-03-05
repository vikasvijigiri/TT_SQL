SELECT 
    material,
    prod_desc,
    doh,
    reporting_date
FROM 
    "acme-chatbot".doh
WHERE 
    material = 40520
ORDER BY 
    reporting_date DESC
LIMIT 1