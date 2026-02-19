WITH qualified_countries AS (
    SELECT Country
    FROM customers
    GROUP BY Country
    HAVING COUNT(DISTINCT CustomerId) > 4
),
country_sales AS (
    SELECT c.Country, SUM(i.Total) AS total_sales
    FROM invoices i
    JOIN customers c ON i.CustomerId = c.CustomerId
    WHERE c.Country IN (SELECT Country FROM qualified_countries)
    GROUP BY c.Country
),
ranked AS (
    SELECT total_sales,
           ROW_NUMBER() OVER (ORDER BY total_sales) AS rn,
           COUNT(*) OVER () AS cnt
    FROM country_sales
)
SELECT AVG(total_sales) AS median_total_sales
FROM ranked
WHERE rn = CAST((cnt + 1) / 2 AS INTEGER) OR rn = CAST((cnt + 2) / 2 AS INTEGER);