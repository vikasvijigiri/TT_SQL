SELECT 
  ROUND(SUM(shipped_3m::bigint) * 100.0 / NULLIF(SUM(demand_3m::bigint), 0), 2) AS overall_fill_rate_percent
FROM "acme-chatbot"."demand-forecast"