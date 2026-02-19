WITH base AS (
  SELECT s.prod_id,
         s.amount_sold,
         c.cust_city,
         t.calendar_quarter_id
  FROM sales s
  JOIN customers c ON s.cust_id = c.cust_id
  JOIN countries cn ON c.country_id = cn.country_id
  JOIN times t ON s.time_id = t.time_id
  WHERE s.promo_id = 999
    AND LOWER(cn.country_name) = 'united states'
    AND t.calendar_quarter_id IN (1772, 1776)
),
city_sales AS (
  SELECT cust_city,
         SUM(CASE WHEN calendar_quarter_id = 1772 THEN amount_sold ELSE 0 END) AS sales_2019,
         SUM(CASE WHEN calendar_quarter_id = 1776 THEN amount_sold ELSE 0 END) AS sales_2020
  FROM base
  GROUP BY cust_city
),
qualified_cities AS (
  SELECT cust_city
  FROM city_sales
  WHERE sales_2019 > 0
    AND (sales_2020 - sales_2019) / sales_2019 >= 0.20
),
sales_q AS (
  SELECT prod_id,
         amount_sold,
         calendar_quarter_id,
         cust_city
  FROM base
  WHERE cust_city IN (SELECT cust_city FROM qualified_cities)
),
product_sales AS (
  SELECT prod_id,
         SUM(CASE WHEN calendar_quarter_id = 1772 THEN amount_sold ELSE 0 END) AS product_sales_2019,
         SUM(CASE WHEN calendar_quarter_id = 1776 THEN amount_sold ELSE 0 END) AS product_sales_2020,
         (SUM(CASE WHEN calendar_quarter_id = 1772 THEN amount_sold ELSE 0 END) +
          SUM(CASE WHEN calendar_quarter_id = 1776 THEN amount_sold ELSE 0 END)) AS combined_sales
  FROM sales_q
  GROUP BY prod_id
),
total_sales AS (
  SELECT SUM(CASE WHEN calendar_quarter_id = 1772 THEN amount_sold ELSE 0 END) AS total_sales_2019,
         SUM(CASE WHEN calendar_quarter_id = 1776 THEN amount_sold ELSE 0 END) AS total_sales_2020
  FROM sales_q
),
product_metrics AS (
  SELECT ps.prod_id,
         p.prod_name,
         ps.product_sales_2019,
         ps.product_sales_2020,
         ps.combined_sales,
         ts.total_sales_2019,
         ts.total_sales_2020,
         (ps.product_sales_2019 / ts.total_sales_2019) AS share_2019,
         (ps.product_sales_2020 / ts.total_sales_2020) AS share_2020,
         ((ps.product_sales_2020 / ts.total_sales_2020) - (ps.product_sales_2019 / ts.total_sales_2019)) * 100.0 AS delta_share,
         ROW_NUMBER() OVER (ORDER BY ps.combined_sales DESC) AS rn,
         COUNT(*) OVER () AS total_products
  FROM product_sales ps
  CROSS JOIN total_sales ts
  JOIN products p ON ps.prod_id = p.prod_id
),
top_products AS (
  SELECT *
  FROM product_metrics
  WHERE rn <= total_products * 0.2
)
SELECT prod_id,
       prod_name,
       delta_share
FROM top_products
ORDER BY ABS(delta_share) ASC
LIMIT 1;