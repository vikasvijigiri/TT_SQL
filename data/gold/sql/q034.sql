SELECT prod_family, SUM(monthend_invent) AS total_inventory
FROM "acme-chatbot"."demand-forecast"
GROUP BY prod_family
ORDER BY total_inventory DESC