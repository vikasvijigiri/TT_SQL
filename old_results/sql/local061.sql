WITH sales_data AS (
    SELECT 
        s.prod_id,
        t.calendar_month_number AS month,
        t.calendar_year AS year,
        SUM(s.amount_sold) AS total_sales
    FROM sales s
    JOIN promotions p ON s.promo_id = p.promo_id
    JOIN channels c ON s.channel_id = c.channel_id
    JOIN times t ON s.time_id = t.time_id
    JOIN customers cu ON s.cust_id = cu.cust_id
    JOIN countries co ON cu.country_id = co.country_id
    WHERE co.country_name = 'France'
      AND p.promo_total_id = 1
      AND c.channel_total_id = 1
      AND t.calendar_year IN (2019, 2020)
    GROUP BY s.prod_id, t.calendar_month_number, t.calendar_year
),
projected_growth AS (
    SELECT 
        sd2020.prod_id,
        sd2020.month,
        CASE 
            WHEN sd2019.total_sales IS NULL OR sd2019.total_sales = 0 THEN NULL
            ELSE (CAST(sd2020.total_sales AS REAL) - sd2019.total_sales) / CAST(sd2019.total_sales AS REAL)
        END AS growth_rate
    FROM sales_data sd2020
    LEFT JOIN sales_data sd2019 ON sd2020.prod_id = sd2019.prod_id
        AND sd2020.month = sd2019.month
        AND sd2019.year = 2019
    WHERE sd2020.year = 2020
),
projected_sales AS (
    SELECT 
        pg.prod_id,
        pg.month,
        CASE 
            WHEN pg.growth_rate IS NULL THEN sd2020.total_sales
            ELSE sd2020.total_sales * (1 + pg.growth_rate)
        END AS projected_sales_2021
    FROM projected_growth pg
    JOIN sales_data sd2020 ON pg.prod_id = sd2020.prod_id
        AND pg.month = sd2020.month
        AND sd2020.year = 2020
),
converted_sales AS (
    SELECT 
        ps.month,
        ps.projected_sales_2021 * cu.to_us AS projected_sales_usd
    FROM projected_sales ps
    JOIN currency cu ON cu.country = 'France'
        AND cu.year = 2021
        AND cu.month = ps.month
        AND cu.to_us IS NOT NULL
)
SELECT 
    cs.month,
    AVG(cs.projected_sales_usd) AS average_projected_sales_usd
FROM converted_sales cs
GROUP BY cs.month
ORDER BY cs.month;