SELECT AVG(demand_qty) AS avg_demand_high_priority
FROM "acme-chatbot"."material-packing-tracker"
WHERE priority >= 3