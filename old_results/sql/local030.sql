WITH city_payments AS (
    SELECT 
        c.customer_city AS city,
        SUM(p.payment_value) AS total_payments
    FROM 
        olist_orders o
    JOIN 
        olist_order_payments p ON o.order_id = p.order_id
    JOIN 
        olist_customers c ON o.customer_id = c.customer_id
    WHERE 
        o.order_status = 'delivered'
    GROUP BY 
        c.customer_city
),
city_orders AS (
    SELECT 
        c.customer_city AS city,
        COUNT(DISTINCT o.order_id) AS total_delivered_orders
    FROM 
        olist_orders o
    JOIN 
        olist_customers c ON o.customer_id = c.customer_id
    WHERE 
        o.order_status = 'delivered'
    GROUP BY 
        c.customer_city
),
lowest_cities AS (
    SELECT 
        cp.city,
        cp.total_payments,
        co.total_delivered_orders
    FROM 
        city_payments cp
    JOIN 
        city_orders co ON cp.city = co.city
    ORDER BY 
        cp.total_payments ASC
    LIMIT 5
)
SELECT 
    AVG(total_payments) AS avg_total_payments,
    AVG(total_delivered_orders) AS avg_total_delivered_orders
FROM 
    lowest_cities;