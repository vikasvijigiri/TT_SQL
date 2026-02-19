WITH city_sales AS (
    SELECT c.cust_city AS city,
           t.calendar_year AS year,
           SUM(s.amount_sold) AS city_total_sales
    FROM sales s
    JOIN customers c ON s.cust_id = c.cust_id
    JOIN countries cn ON c.country_id = cn.country_id
    JOIN times t ON s.time_id = t.time_id
    WHERE s.promo_id IS NULL
      AND LOWER(cn.country_name) = 'united states'
      AND LOWER(t.calendar_quarter_desc) = 'q4'
      AND t.calendar_year IN (2019, 2020)
    GROUP BY c.cust_city, t.calendar_year
),
city_growth AS (
    SELECT city,
           SUM(CASE WHEN year = 2019 THEN city_total_sales END) AS sales_2019,
           SUM(CASE WHEN year = 2020 THEN city_total_sales END) AS sales_2020
    FROM city_sales
    GROUP BY city
    HAVING sales_2019 > 0
       AND sales_2020 >= sales_2019 * 1.2
),
product_sales AS (
    SELECT s.prod_id AS prod_id,
           t.calendar_year AS year,
           SUM(s.amount_sold) AS product_total_sales
    FROM sales s
    JOIN customers c ON s.cust_id = c.cust_id
    JOIN countries cn ON c.country_id = cn.country_id
    JOIN times t ON s.time_id = t.time_id
    WHERE s.promo_id IS NULL
      AND LOWER(cn.country_name) = 'united states'
      AND LOWER(t.calendar_quarter_desc) = 'q4'
      AND t.calendar_year IN (2019, 2020)
      AND c.cust_city IN (SELECT city FROM city_growth)
    GROUP BY s.prod_id, t.calendar_year
),
product_combined AS (
    SELECT prod_id,
           SUM(product_total_sales) AS combined_sales
    FROM product_sales
    GROUP BY prod_id
),
ranked_products AS (
    SELECT prod_id,
           combined_sales,
           ROW_NUMBER() OVER (ORDER BY combined_sales DESC) AS rn,
           COUNT(*) OVER () AS total_cnt
    FROM product_combined
),
top_products AS (
    SELECT prod_id
    FROM ranked_products
    WHERE rn <= CAST(total_cnt * 0.2 AS INTEGER)
),
total_sales_by_year AS (
    SELECT t.calendar_year AS year,
           SUM(s.amount_sold) AS total_sales
    FROM sales s
    JOIN customers c ON s.cust_id = c.cust_id
    JOIN countries cn ON c.country_id = cn.country_id
    JOIN times t ON s.time_id = t.time_id
    WHERE s.promo_id IS NULL
      AND LOWER(cn.country_name) = 'united states'
      AND LOWER(t.calendar_quarter_desc) = 'q4'
      AND t.calendar_year IN (2019, 2020)
      AND c.cust_city IN (SELECT city FROM city_growth)
    GROUP BY t.calendar_year
),
product_shares AS (
    SELECT ps.prod_id,
           MAX(CASE WHEN ps.year = 2019 THEN ps.product_total_sales / ts.total_sales END) AS share_2019,
           MAX(CASE WHEN ps.year = 2020 THEN ps.product_total_sales / ts.total_sales END) AS share_2020,
           MAX(CASE WHEN ps.year = 2020 THEN ps.product_total_sales / ts.total_sales END) -
           MAX(CASE WHEN ps.year = 2019 THEN ps.product_total_sales / ts.total_sales END) AS share_change
    FROM product_sales ps
    JOIN total_sales_by_year ts ON ps.year = ts.year
    WHERE ps.prod_id IN (SELECT prod_id FROM top_products)
    GROUP BY ps.prod_id
)
SELECT p.prod_id,
       p.prod_name,
       ps.share_2019,
       ps.share_2020,
       ps.share_change
FROM product_shares ps
JOIN products p ON ps.prod_id = p.prod_id
ORDER BY ps.share_change DESC;