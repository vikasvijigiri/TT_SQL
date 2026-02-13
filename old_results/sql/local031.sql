WITH annual_delivered_orders AS (
    SELECT 
        strftime('%Y', order_delivered_customer_date) AS year, 
        COUNT(order_id) AS total_orders
    FROM 
        olist_orders
    WHERE 
        order_status = 'delivered'
        AND strftime('%Y', order_delivered_customer_date) IN ('2016', '2017', '2018')
    GROUP BY 
        year
),
min_year AS (
    SELECT 
        year
    FROM 
        annual_delivered_orders
    ORDER BY 
        total_orders ASC
    LIMIT 1
),
monthly_delivered_orders AS (
    SELECT 
        strftime('%Y', order_delivered_customer_date) AS year, 
        strftime('%m', order_delivered_customer_date) AS month, 
        COUNT(order_id) AS monthly_orders
    FROM 
        olist_orders
    WHERE 
        order_status = 'delivered'
        AND strftime('%Y', order_delivered_customer_date) IN ('2016', '2017', '2018')
    GROUP BY 
        year, month
)
SELECT 
    MAX(monthly_orders) AS highest_monthly_orders
FROM 
    monthly_delivered_orders
WHERE 
    year = (SELECT year FROM min_year);