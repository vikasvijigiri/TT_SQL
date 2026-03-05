WITH this_month_inventory AS (
    SELECT 
        material,
        prod_desc,
        prod_family,
        monthend_invent,
        month,
        LEAD(month) OVER (PARTITION BY material ORDER BY month) AS next_month
    FROM 
        "acme-chatbot"."demand-forecast"
),
next_month_demand AS (
    SELECT 
        material,
        month AS demand_month,
        demand AS forecasted_demand
    FROM 
        "acme-chatbot"."demand-forecast"
),
inventory_vs_demand AS (
    SELECT 
        i.material,
        i.prod_desc,
        i.prod_family,
        TO_CHAR(i.month, 'YYYY-MM') AS inventory_month,
        TO_CHAR(i.next_month, 'YYYY-MM') AS forecast_month,
        i.monthend_invent,
        d.forecasted_demand,
        CASE 
            WHEN i.monthend_invent >= d.forecasted_demand THEN 'Sufficient'
            ELSE 'Insufficient'
        END AS inventory_status
    FROM 
        this_month_inventory i
    LEFT JOIN 
        next_month_demand d 
        ON i.material = d.material AND i.next_month = d.demand_month
)
SELECT *
FROM inventory_vs_demand
ORDER BY inventory_status DESC, forecasted_demand DESC