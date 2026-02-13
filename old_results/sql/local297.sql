WITH MonthlyNet AS (
    SELECT 
        customer_id,
        strftime('%Y-%m', txn_date) AS month_year,
        SUM(CASE WHEN txn_type = 'deposit' THEN txn_amount 
                 WHEN txn_type = 'withdrawal' THEN -txn_amount 
                 ELSE 0 END) AS net_amount
    FROM customer_transactions
    GROUP BY customer_id, month_year
),
CumulativeBalance AS (
    SELECT 
        customer_id,
        month_year,
        net_amount,
        SUM(net_amount) OVER (PARTITION BY customer_id ORDER BY month_year) AS closing_balance
    FROM MonthlyNet
),
RecentGrowth AS (
    SELECT 
        customer_id,
        month_year,
        closing_balance,
        LAG(closing_balance) OVER (PARTITION BY customer_id ORDER BY month_year) AS prev_closing_balance,
        CASE 
            WHEN LAG(closing_balance) OVER (PARTITION BY customer_id ORDER BY month_year) IS NULL OR LAG(closing_balance) OVER (PARTITION BY customer_id ORDER BY month_year) = 0 THEN 
                CASE WHEN closing_balance > 0 THEN 100.0 ELSE 0 END
            ELSE ((closing_balance - LAG(closing_balance) OVER (PARTITION BY customer_id ORDER BY month_year)) * 100.0 / CAST(LAG(closing_balance) OVER (PARTITION BY customer_id ORDER BY month_year) AS REAL))
        END AS growth_rate
    FROM CumulativeBalance
),
MostRecentMonth AS (
    SELECT 
        customer_id,
        MAX(month_year) AS most_recent_month
    FROM CumulativeBalance
    GROUP BY customer_id
),
GrowthAbove5Percent AS (
    SELECT 
        rg.customer_id
    FROM RecentGrowth rg
    INNER JOIN MostRecentMonth mrm ON rg.customer_id = mrm.customer_id AND rg.month_year = mrm.most_recent_month
    WHERE rg.growth_rate > 5
)
SELECT 
    CAST(COUNT(DISTINCT g.customer_id) AS REAL) * 100.0 / CAST(COUNT(DISTINCT r.customer_id) AS REAL) AS percentage_above_5_percent
FROM RecentGrowth r
INNER JOIN MostRecentMonth mrm ON r.customer_id = mrm.customer_id AND r.month_year = mrm.most_recent_month
LEFT JOIN GrowthAbove5Percent g ON r.customer_id = g.customer_id
WHERE r.month_year = mrm.most_recent_month;