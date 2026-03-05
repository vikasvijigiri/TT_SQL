SELECT material, prod_desc, demand_3m, shipped_3m
FROM "acme-chatbot"."demand-forecast"
WHERE demand_3m > 0 AND (shipped_3m IS NULL OR shipped_3m = 0)