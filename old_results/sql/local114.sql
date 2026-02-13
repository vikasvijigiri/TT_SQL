WITH RegionalSales AS (
    SELECT
        hdc.region AS region_name,
        wo.id AS order_id,
        wo.total_amt_usd AS order_total,
        ws.id AS sales_rep_id,
        ws.name AS sales_rep_name
    FROM web_orders wo
    JOIN web_accounts wa ON wo.account_id = wa.id
    JOIN web_sales_reps ws ON wa.sales_rep_id = ws.id
    JOIN hardware_dim_customer hdc ON wa.id = hdc.customer_code
),
RegionalSummary AS (
    SELECT
        region_name,
        COUNT(order_id) AS number_of_orders,
        SUM(order_total) AS total_sales_amount
    FROM RegionalSales
    GROUP BY region_name
),
SalesRepSummary AS (
    SELECT
        region_name,
        sales_rep_id,
        sales_rep_name,
        SUM(order_total) AS sales_rep_total
    FROM RegionalSales
    GROUP BY region_name, sales_rep_id, sales_rep_name
),
TopSalesReps AS (
    SELECT
        region_name,
        sales_rep_name,
        sales_rep_total,
        DENSE_RANK() OVER (PARTITION BY region_name ORDER BY sales_rep_total DESC) AS sales_rank
    FROM SalesRepSummary
)
SELECT
    rs.region_name,
    rs.number_of_orders,
    rs.total_sales_amount,
    tsr.sales_rep_name,
    tsr.sales_rep_total
FROM RegionalSummary rs
JOIN TopSalesReps tsr ON rs.region_name = tsr.region_name
WHERE tsr.sales_rank = 1
ORDER BY rs.region_name, tsr.sales_rep_total DESC;