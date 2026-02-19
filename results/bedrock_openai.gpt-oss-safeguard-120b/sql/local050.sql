WITH base AS (
  SELECT s.amount_sold,
         t.calendar_year,
         t.calendar_month_number AS month,
         c.country_name,
         p.promo_total_id,
         ch.channel_total_id
  FROM sales s
  JOIN times t ON s.time_id = t.time_id
  JOIN customers cu ON s.cust_id = cu.cust_id
  JOIN countries c ON cu.country_id = c.country_id
  JOIN promotions p ON s.promo_id = p.promo_id
  JOIN channels ch ON s.channel_id = ch.channel_id
  WHERE LOWER(c.country_name) = 'france'
    AND p.promo_total_id = 1
    AND ch.channel_total_id = 1
    AND t.calendar_year IN (2019, 2020)
),
monthly_totals AS (
  SELECT calendar_year,
         month,
         SUM(amount_sold) AS total_sales
  FROM base
  GROUP BY calendar_year, month
),
 growth_factor AS (
  SELECT CAST(SUM(CASE WHEN calendar_year = 2020 THEN total_sales END) AS REAL) /
         NULLIF(SUM(CASE WHEN calendar_year = 2019 THEN total_sales END), 0) AS factor
  FROM monthly_totals
),
projected_2021 AS (
  SELECT mt.month,
         mt.total_sales * gf.factor AS projected_sales
  FROM monthly_totals mt
  JOIN growth_factor gf ON 1 = 1
  WHERE mt.calendar_year = 2020
),
projected_usd AS (
  SELECT p.month,
         p.projected_sales * cur.to_us AS projected_usd
  FROM projected_2021 p
  JOIN currency cur ON LOWER(cur.country) = 'france'
                     AND cur.year = 2021
                     AND cur.month = p.month
),
ranked AS (
  SELECT projected_usd,
         ROW_NUMBER() OVER (ORDER BY projected_usd) AS rn,
         COUNT(*) OVER () AS cnt
  FROM projected_usd
)
SELECT AVG(projected_usd) AS median_projected_usd
FROM ranked
WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2);