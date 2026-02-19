WITH italian_customers AS (
    SELECT c.cust_id
    FROM customers c
    JOIN countries cn ON c.country_id = cn.country_id
    WHERE LOWER(cn.country_name) = 'italy'
),
customer_profits AS (
    SELECT s.cust_id,
           SUM(s.quantity_sold * (co.unit_price - co.unit_cost)) AS total_profit
    FROM sales s
    JOIN italian_customers ic ON s.cust_id = ic.cust_id
    JOIN times t ON s.time_id = t.time_id
    JOIN costs co ON s.prod_id = co.prod_id AND s.time_id = co.time_id
    WHERE LOWER(t.calendar_month_name) = 'december'
      AND t.calendar_year = 2021
    GROUP BY s.cust_id
),
profit_stats AS (
    SELECT MIN(total_profit) AS min_profit,
           MAX(total_profit) AS max_profit
    FROM customer_profits
),
bucketed AS (
    SELECT cp.cust_id,
           cp.total_profit,
           CASE
               WHEN ps.max_profit = ps.min_profit THEN 0
               ELSE MIN(9, CAST((cp.total_profit - ps.min_profit) / ((ps.max_profit - ps.min_profit) / 10.0) AS INTEGER))
           END AS bucket_number
    FROM customer_profits cp
    CROSS JOIN profit_stats ps
)
SELECT bucket_number,
       COUNT(*) AS customer_count,
       MIN(total_profit) AS min_total_profit,
       MAX(total_profit) AS max_total_profit
FROM bucketed
GROUP BY bucket_number
ORDER BY bucket_number;