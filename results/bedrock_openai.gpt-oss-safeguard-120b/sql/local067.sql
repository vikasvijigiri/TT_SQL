WITH customer_profits AS (
    SELECT c.cust_id,
           SUM(s.amount_sold - (s.quantity_sold * co.unit_cost)) AS total_profit
    FROM customers c
    JOIN countries cn ON c.country_id = cn.country_id
    JOIN sales s ON c.cust_id = s.cust_id
    JOIN times t ON s.time_id = t.time_id
    JOIN costs co ON s.prod_id = co.prod_id
               AND s.time_id = co.time_id
               AND s.channel_id = co.channel_id
               AND s.promo_id = co.promo_id
    WHERE LOWER(cn.country_name) = 'italy'
      AND LOWER(t.calendar_month_name) = 'december'
      AND t.calendar_year = 2021
    GROUP BY c.cust_id
), tiered_profits AS (
    SELECT total_profit,
           NTILE(10) OVER (ORDER BY total_profit) AS tier_number
    FROM customer_profits
)
SELECT tier_number,
       MAX(total_profit) AS highest_profit,
       MIN(total_profit) AS lowest_profit
FROM tiered_profits
GROUP BY tier_number
ORDER BY tier_number;