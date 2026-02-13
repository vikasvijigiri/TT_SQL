WITH Q4_2019 AS (
    SELECT time_id
    FROM times
    WHERE calendar_year = 2019 AND calendar_quarter_desc = 'Q4'
),
Q4_2020 AS (
    SELECT time_id
    FROM times
    WHERE calendar_year = 2020 AND calendar_quarter_desc = 'Q4'
),
US_Sales_2019 AS (
    SELECT c.cust_city, s.prod_id, SUM(s.amount_sold) AS total_sales_2019
    FROM sales s
    JOIN customers c ON s.cust_id = c.cust_id
    WHERE s.time_id IN (SELECT time_id FROM Q4_2019) AND s.promo_id IS NULL AND c.country_id = 1
    GROUP BY c.cust_city, s.prod_id
),
US_Sales_2020 AS (
    SELECT c.cust_city, s.prod_id, SUM(s.amount_sold) AS total_sales_2020
    FROM sales s
    JOIN customers c ON s.cust_id = c.cust_id
    WHERE s.time_id IN (SELECT time_id FROM Q4_2020) AND s.promo_id IS NULL AND c.country_id = 1
    GROUP BY c.cust_city, s.prod_id
),
City_Sales_Increase AS (
    SELECT us19.cust_city
    FROM US_Sales_2019 us19
    JOIN US_Sales_2020 us20 ON us19.cust_city = us20.cust_city
    GROUP BY us19.cust_city
    HAVING SUM(us20.total_sales_2020) >= 1.2 * SUM(us19.total_sales_2019)
),
Product_Sales AS (
    SELECT us20.prod_id, 
           SUM(us20.total_sales_2020) AS total_sales_2020,
           SUM(COALESCE(us19.total_sales_2019, 0)) AS total_sales_2019
    FROM US_Sales_2020 us20
    LEFT JOIN US_Sales_2019 us19 ON us20.prod_id = us19.prod_id AND us20.cust_city = us19.cust_city
    WHERE us20.cust_city IN (SELECT cust_city FROM City_Sales_Increase)
    GROUP BY us20.prod_id
),
Ranked_Products AS (
    SELECT prod_id, total_sales_2020 + total_sales_2019 AS total_sales,
           ROW_NUMBER() OVER (ORDER BY total_sales_2020 + total_sales_2019 DESC) AS rank,
           COUNT(*) OVER () AS total_count
    FROM Product_Sales
),
Top_Products AS (
    SELECT prod_id
    FROM Ranked_Products
    WHERE rank <= total_count * 0.2
),
Product_Share_Change AS (
    SELECT tp.prod_id, 
           SUM(COALESCE(us19.total_sales_2019, 0)) / CAST((SELECT SUM(total_sales_2019) FROM US_Sales_2019 WHERE cust_city IN (SELECT cust_city FROM City_Sales_Increase)) AS REAL) AS share_2019,
           SUM(us20.total_sales_2020) / CAST((SELECT SUM(total_sales_2020) FROM US_Sales_2020 WHERE cust_city IN (SELECT cust_city FROM City_Sales_Increase)) AS REAL) AS share_2020
    FROM Top_Products tp
    LEFT JOIN US_Sales_2019 us19 ON tp.prod_id = us19.prod_id
    LEFT JOIN US_Sales_2020 us20 ON tp.prod_id = us20.prod_id
    GROUP BY tp.prod_id
)
SELECT prod_id, share_2020 - share_2019 AS share_change
FROM Product_Share_Change
ORDER BY share_change DESC;