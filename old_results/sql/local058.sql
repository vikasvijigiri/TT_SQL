WITH UniqueSalesProducts2020 AS (
    SELECT segment, COUNT(DISTINCT product_code) AS unique_sales_product_count_2020
    FROM hardware_dim_product
    JOIN hardware_fact_sales_monthly ON hardware_dim_product.product_code = hardware_fact_sales_monthly.product_code
    WHERE fiscal_year = 2020
    GROUP BY segment
),
UniqueSalesProducts2021 AS (
    SELECT segment, COUNT(DISTINCT product_code) AS unique_sales_product_count_2021
    FROM hardware_dim_product
    JOIN hardware_fact_sales_monthly ON hardware_dim_product.product_code = hardware_fact_sales_monthly.product_code
    WHERE fiscal_year = 2021
    GROUP BY segment
),
PercentageIncrease AS (
    SELECT 
        u2020.segment,
        u2020.unique_sales_product_count_2020,
        u2021.unique_sales_product_count_2021,
        CASE 
            WHEN u2020.unique_sales_product_count_2020 > 0 THEN 
                ((u2021.unique_sales_product_count_2021 - u2020.unique_sales_product_count_2020) / CAST(u2020.unique_sales_product_count_2020 AS REAL)) * 100
            ELSE 
                NULL
        END AS percentage_increase
    FROM UniqueSalesProducts2020 u2020
    JOIN UniqueSalesProducts2021 u2021 ON u2020.segment = u2021.segment
)
SELECT segment, unique_sales_product_count_2020, unique_sales_product_count_2021, percentage_increase
FROM PercentageIncrease
ORDER BY percentage_increase DESC;