SELECT 
  DATE_TRUNC('month', "month") AS month,
  SUM(demand) AS total_demand
FROM "acme-chatbot"."demand-forecast"
WHERE "month" = DATE_TRUNC('month', CURRENT_DATE)
GROUP BY month