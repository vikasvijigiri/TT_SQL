WITH filtered_sales AS (
    SELECT s.prod_id,
           t.calendar_year,
           t.calendar_month_number AS month,
           s.amount_sold
    FROM sales s
    JOIN customers c ON s.cust_id = c.cust_id
    JOIN countries cn ON c.country_id = cn.country_id
    JOIN times t ON s.time_id = t.time_id
    JOIN promotions p ON s.promo_id = p.promo_id
    JOIN channels ch ON s.channel_id = ch.channel_id
    WHERE LOWER(cn.country_name) = 'france'
      AND p.promo_total_id = 1
      AND ch.channel_total_id = 1
      AND t.calendar_year IN (2019, 2020)
),
sales_agg AS (
    SELECT prod_id,
           month,
           SUM(CASE WHEN calendar_year = 2019 THEN amount_sold END) AS sales_2019,
           SUM(CASE WHEN calendar_year = 2020 THEN amount_sold END) AS sales_2020
    FROM filtered_sales
    GROUP BY prod_id, month
),
projected AS (
    SELECT prod_id,
           month,
           sales_2020,
           sales_2019,
           (sales_2020 - sales_2019) / NULLIF(CAST(sales_2019 AS REAL), 0) AS growth_rate,
           sales_2020 * (1 + ((sales_2020 - sales_2019) / NULLIF(CAST(sales_2019 AS REAL), 0))) AS projected_2021
    FROM sales_agg
    WHERE sales_2020 IS NOT NULL
),
projected_usd AS (
    SELECT p.month,
           p.projected_2021 * cr.to_us AS projected_2021_usd
    FROM projected p
    JOIN currency cr ON LOWER(cr.country) = 'france' AND cr.year = 2021 AND cr.month = p.month
)
SELECT month,
       AVG(projected_2021_usd) AS average_projected_sales_usd
FROM projected_usd
GROUP BY month
ORDER BY month;