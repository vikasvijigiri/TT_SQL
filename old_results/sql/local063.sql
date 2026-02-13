WITH FilteredSales AS (
    SELECT s.prod_id, c.cust_city_id, t.calendar_quarter_id, SUM(s.amount_sold) AS total_sales
    FROM sales s
    JOIN times t ON s.time_id = t.time_id
    JOIN customers c ON s.cust_id = c.cust_id
    JOIN countries co ON c.country_id = co.country_id
    WHERE s.promo_id = 999
      AND co.country_name = 'United States'
      AND t.calendar_quarter_id IN (1772, 1776)
    GROUP BY s.prod_id, c.cust_city_id, t.calendar_quarter_id
),
CitySalesIncrease AS (
    SELECT f1.cust_city_id, 
           (SUM(f2.total_sales) - SUM(f1.total_sales)) / CAST(SUM(f1.total_sales) AS REAL) AS sales_increase
    FROM FilteredSales f1
    JOIN FilteredSales f2 ON f1.cust_city_id = f2.cust_city_id
    WHERE f1.calendar_quarter_id = 1772 AND f2.calendar_quarter_id = 1776
    GROUP BY f1.cust_city_id
),
TopCities AS (
    SELECT cust_city_id
    FROM CitySalesIncrease
    WHERE sales_increase >= 0.20
),
ProductSales AS (
    SELECT f.prod_id, SUM(f.total_sales) AS total_sales
    FROM FilteredSales f
    JOIN TopCities tc ON f.cust_city_id = tc.cust_city_id
    GROUP BY f.prod_id
),
RankedProducts AS (
    SELECT prod_id, total_sales, 
           NTILE(5) OVER (ORDER BY total_sales DESC) AS sales_rank
    FROM ProductSales
),
TopProducts AS (
    SELECT prod_id
    FROM RankedProducts
    WHERE sales_rank = 1
),
ProductShareChange AS (
    SELECT f1.prod_id, 
           (f2.total_sales / CAST((SELECT SUM(total_sales) FROM FilteredSales WHERE calendar_quarter_id = 1776 AND cust_city_id IN (SELECT cust_city_id FROM TopCities)) AS REAL)) -
           (f1.total_sales / CAST((SELECT SUM(total_sales) FROM FilteredSales WHERE calendar_quarter_id = 1772 AND cust_city_id IN (SELECT cust_city_id FROM TopCities)) AS REAL)) AS share_change
    FROM FilteredSales f1
    JOIN FilteredSales f2 ON f1.prod_id = f2.prod_id AND f1.cust_city_id = f2.cust_city_id
    WHERE f1.calendar_quarter_id = 1772 AND f2.calendar_quarter_id = 1776
      AND f1.prod_id IN (SELECT prod_id FROM TopProducts)
      AND f1.cust_city_id IN (SELECT cust_city_id FROM TopCities)
)
SELECT p.prod_id, p.prod_name, ps.share_change
FROM ProductShareChange ps
JOIN products p ON ps.prod_id = p.prod_id
ORDER BY ABS(ps.share_change) ASC
LIMIT 1;