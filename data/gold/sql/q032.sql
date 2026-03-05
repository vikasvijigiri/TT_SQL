SELECT 
  prod_family,
  DATE_TRUNC('month', "month") AS forecast_month,
  ROUND(AVG(month_end_doh::bigint), 2) AS avg_doh
FROM "acme-chatbot"."demand-forecast"
GROUP BY prod_family, forecast_month
ORDER BY forecast_month