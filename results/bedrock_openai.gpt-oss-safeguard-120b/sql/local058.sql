SELECT
    p.segment,
    COUNT(DISTINCT CASE WHEN f.fiscal_year = 2020 THEN f.product_code END) AS unique_count_2020,
    COUNT(DISTINCT CASE WHEN f.fiscal_year = 2021 THEN f.product_code END) AS unique_count_2021,
    CASE WHEN COUNT(DISTINCT CASE WHEN f.fiscal_year = 2020 THEN f.product_code END) = 0 THEN NULL
         ELSE ((COUNT(DISTINCT CASE WHEN f.fiscal_year = 2021 THEN f.product_code END) - COUNT(DISTINCT CASE WHEN f.fiscal_year = 2020 THEN f.product_code END)) * 100.0 / COUNT(DISTINCT CASE WHEN f.fiscal_year = 2020 THEN f.product_code END))
    END AS pct_increase
FROM hardware_fact_sales_monthly f
JOIN hardware_dim_product p ON f.product_code = p.product_code
WHERE f.fiscal_year IN (2020, 2021)
GROUP BY p.segment
ORDER BY pct_increase DESC;