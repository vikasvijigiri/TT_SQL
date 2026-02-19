WITH sales_2021 AS (
    SELECT product_code, SUM(sold_quantity) AS total_quantity_sold
    FROM hardware_fact_sales_monthly
    WHERE fiscal_year = 2021
    GROUP BY product_code
), product_sales AS (
    SELECT p.division,
           s.product_code,
           s.total_quantity_sold,
           ROW_NUMBER() OVER (PARTITION BY p.division ORDER BY s.total_quantity_sold DESC) AS rn
    FROM sales_2021 s
    JOIN hardware_dim_product p ON p.product_code = s.product_code
), top_three AS (
    SELECT division, total_quantity_sold
    FROM product_sales
    WHERE rn <= 3
)
SELECT division,
       AVG(total_quantity_sold) AS average_quantity_sold
FROM top_three
GROUP BY division
ORDER BY division;