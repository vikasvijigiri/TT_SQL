SELECT prod_family, ROUND(AVG(demand::bigint), 2) AS avg_demand
FROM "acme-chatbot"."demand-forecast"
WHERE EXTRACT(YEAR FROM "month") = EXTRACT(YEAR FROM CURRENT_DATE)
GROUP BY prod_family
ORDER BY avg_demand DESC