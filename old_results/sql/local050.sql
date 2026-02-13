WITH france_sales AS (
    SELECT s.amount_sold, t.calendar_year, t.calendar_month_number
    FROM sales s
    JOIN customers c ON s.cust_id = c.cust_id
    JOIN countries co ON c.country_id = co.country_id
    JOIN times t ON s.time_id = t.time_id
    WHERE co.country_name = 'France'
      AND s.promo_id = 1
      AND s.channel_id = 1
      AND t.calendar_year IN (2019, 2020)
),
monthly_totals AS (
    SELECT calendar_year, calendar_month_number, SUM(amount_sold) AS total_sales
    FROM france_sales
    GROUP BY calendar_year, calendar_month_number
),
average_monthly_sales AS (
    SELECT calendar_year, AVG(total_sales) AS avg_sales
    FROM monthly_totals
    GROUP BY calendar_year
),
growth_rate AS (
    SELECT (y2020.avg_sales - y2019.avg_sales) / y2019.avg_sales AS rate
    FROM average_monthly_sales y2019
    JOIN average_monthly_sales y2020 ON y2019.calendar_year = 2019 AND y2020.calendar_year = 2020
),
projected_2021_sales AS (
    SELECT 2021 AS calendar_year, mt.calendar_month_number, 
           mt.total_sales * (1 + gr.rate) AS projected_sales
    FROM monthly_totals mt
    JOIN growth_rate gr ON mt.calendar_year = 2020
),
converted_sales AS (
    SELECT p.calendar_month_number, p.projected_sales * cu.to_us AS projected_sales_usd
    FROM projected_2021_sales p
    JOIN currency cu ON cu.country = 'France' AND cu.year = 2021 AND cu.month = p.calendar_month_number
),
ranked_sales AS (
    SELECT projected_sales_usd, ROW_NUMBER() OVER (ORDER BY projected_sales_usd) AS rn, COUNT(*) OVER () AS cnt
    FROM converted_sales
)
SELECT AVG(projected_sales_usd) AS median_projected_sales_usd
FROM ranked_sales
WHERE rn IN (CAST((cnt + 1) / 2.0 AS INTEGER), CAST((cnt + 2) / 2.0 AS INTEGER));