WITH ItalianCustomerProfits AS (
    SELECT c.cust_id, 
           SUM(COALESCE(s.amount_sold, 0) - (COALESCE(s.quantity_sold, 0) * COALESCE(costs.unit_cost, 0))) AS profit
    FROM sales s
    JOIN customers c ON s.cust_id = c.cust_id
    JOIN times t ON s.time_id = t.time_id
    LEFT JOIN costs ON s.prod_id = costs.prod_id AND s.time_id = costs.time_id AND s.channel_id = costs.channel_id AND s.promo_id = costs.promo_id
    JOIN countries co ON c.country_id = co.country_id
    WHERE co.country_name = 'Italy'
      AND t.calendar_month_desc = 'December'
      AND t.calendar_year = 2021
    GROUP BY c.cust_id
),
RankedProfits AS (
    SELECT cust_id, 
           profit,
           NTILE(10) OVER (ORDER BY profit DESC) AS tier
    FROM ItalianCustomerProfits
)
SELECT tier, 
       MAX(profit) AS highest_profit, 
       MIN(profit) AS lowest_profit
FROM RankedProfits
GROUP BY tier
ORDER BY tier;