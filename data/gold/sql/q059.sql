SELECT 
    prod_family,
    TO_CHAR("month", 'YYYY-MM') AS forecast_month,
    SUM(demand::bigint) AS total_forecasted_demand,
    SUM(orders::bigint) AS total_actual_orders,
    SUM(orders::bigint - demand::bigint) AS demand_delta,
    ROUND(AVG(orders::bigint - demand::bigint), 2) AS avg_delta_per_product
FROM 
    "acme-chatbot"."demand-forecast"
WHERE 
    "month" >= date_trunc('month', CURRENT_DATE - INTERVAL '3 months')
GROUP BY 
    prod_family, TO_CHAR("month", 'YYYY-MM')
ORDER BY 
    forecast_month, prod_family