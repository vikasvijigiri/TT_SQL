WITH MonthlyTransactions AS (
    SELECT 
        customer_id, 
        strftime('%Y-%m', txn_date) AS year_month, 
        SUM(CASE WHEN txn_type = 'credit' THEN txn_amount ELSE -txn_amount END) AS monthly_change
    FROM 
        customer_transactions
    GROUP BY 
        customer_id, year_month
),
AllMonths AS (
    SELECT DISTINCT 
        strftime('%Y-%m', txn_date) AS year_month
    FROM 
        customer_transactions
),
CustomerMonths AS (
    SELECT 
        customer_id, 
        year_month
    FROM 
        (SELECT DISTINCT customer_id FROM customer_transactions) 
    CROSS JOIN 
        AllMonths
),
MonthlyBalances AS (
    SELECT 
        cm.customer_id, 
        cm.year_month, 
        COALESCE(mt.monthly_change, 0) AS monthly_change
    FROM 
        CustomerMonths cm
    LEFT JOIN 
        MonthlyTransactions mt 
    ON 
        cm.customer_id = mt.customer_id 
        AND cm.year_month = mt.year_month
),
CumulativeBalances AS (
    SELECT 
        mb.customer_id, 
        mb.year_month, 
        mb.monthly_change, 
        SUM(mb.monthly_change) OVER (PARTITION BY mb.customer_id ORDER BY mb.year_month) AS cumulative_balance
    FROM 
        MonthlyBalances mb
)
SELECT 
    customer_id, 
    year_month, 
    monthly_change, 
    cumulative_balance
FROM 
    CumulativeBalances
ORDER BY 
    customer_id, year_month;