WITH Italian_Customers_Profits AS (
    SELECT c.cust_id, 
           SUM(s.quantity_sold * (co.unit_price - co.unit_cost)) AS total_profit
    FROM sales s
    JOIN customers c ON s.cust_id = c.cust_id
    JOIN costs co ON s.prod_id = co.prod_id AND s.time_id = co.time_id
    JOIN times t ON s.time_id = t.time_id
    JOIN countries cn ON c.country_id = cn.country_id
    WHERE cn.country_name = 'Italy'
      AND t.calendar_month_number = 12
      AND t.calendar_year = 2021
    GROUP BY c.cust_id
),
Profit_Range AS (
    SELECT MIN(total_profit) AS min_profit, MAX(total_profit) AS max_profit
    FROM Italian_Customers_Profits
),
Profit_Buckets AS (
    SELECT icp.cust_id, icp.total_profit,
           CASE 
               WHEN pr.max_profit = pr.min_profit THEN 0
               ELSE CAST((icp.total_profit - pr.min_profit) AS REAL) / (pr.max_profit - pr.min_profit) * 10
           END AS bucket
    FROM Italian_Customers_Profits icp, Profit_Range pr
),
Bucket_Intervals AS (
    SELECT pr.min_profit + (pr.max_profit - pr.min_profit) * (b.bucket / 10.0) AS lower_bound,
           pr.min_profit + (pr.max_profit - pr.min_profit) * ((b.bucket + 1) / 10.0) AS upper_bound,
           b.bucket
    FROM Profit_Buckets b, Profit_Range pr
    GROUP BY b.bucket
)
SELECT b.bucket + 1 AS bucket,
       COUNT(*) AS number_of_customers,
       MIN(b.total_profit) AS min_profit,
       MAX(b.total_profit) AS max_profit
FROM Profit_Buckets b
JOIN Bucket_Intervals bi ON b.bucket = bi.bucket
WHERE b.total_profit >= bi.lower_bound AND b.total_profit < bi.upper_bound
GROUP BY b.bucket
ORDER BY b.bucket;