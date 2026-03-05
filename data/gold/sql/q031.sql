SELECT material, prod_desc, demand_3m
FROM "acme-chatbot"."demand-forecast"
ORDER BY demand_3m DESC
LIMIT 5