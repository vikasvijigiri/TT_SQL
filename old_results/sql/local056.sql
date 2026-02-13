WITH RankedPayments AS (
    SELECT 
        customer_id, 
        amount, 
        payment_date,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY payment_date) AS rn
    FROM 
        payment
),
MonthlyChanges AS (
    SELECT 
        p1.customer_id,
        (julianday(p2.payment_date) - julianday(p1.payment_date)) / 30.0 AS month_diff,
        (p2.amount - p1.amount) / CAST((julianday(p2.payment_date) - julianday(p1.payment_date)) / 30.0 AS REAL) AS monthly_change
    FROM 
        RankedPayments p1
    JOIN 
        RankedPayments p2 ON p1.customer_id = p2.customer_id AND p2.rn = p1.rn + 1
),
AverageMonthlyChanges AS (
    SELECT 
        customer_id,
        AVG(monthly_change) AS avg_monthly_change
    FROM 
        MonthlyChanges
    GROUP BY 
        customer_id
)
SELECT 
    c.first_name, 
    c.last_name
FROM 
    AverageMonthlyChanges amc
JOIN 
    customer c ON amc.customer_id = c.customer_id
ORDER BY 
    amc.avg_monthly_change DESC
LIMIT 1;