WITH ProductSales AS (
    SELECT 
        p.division, 
        s.product_code, 
        SUM(s.sold_quantity) AS total_quantity_sold
    FROM 
        hardware_fact_sales_monthly s
    JOIN 
        hardware_dim_product p ON s.product_code = p.product_code
    WHERE 
        s.fiscal_year = 2021
    GROUP BY 
        p.division, s.product_code
),
TopProducts AS (
    SELECT 
        division, 
        product_code, 
        total_quantity_sold,
        ROW_NUMBER() OVER (PARTITION BY division ORDER BY total_quantity_sold DESC) AS rn
    FROM 
        ProductSales
),
TopThreeProducts AS (
    SELECT 
        division, 
        product_code, 
        total_quantity_sold
    FROM 
        TopProducts
    WHERE 
        rn <= 3
)
SELECT 
    AVG(total_quantity_sold) AS overall_average_quantity_sold
FROM 
    TopThreeProducts;