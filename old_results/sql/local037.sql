WITH PaymentCategory AS (
    SELECT 
        p.product_category_name, 
        op.payment_type, 
        COUNT(*) AS payment_count
    FROM 
        olist_order_payments op
    JOIN 
        olist_order_items oi ON op.order_id = oi.order_id
    JOIN 
        olist_products p ON oi.product_id = p.product_id
    GROUP BY 
        p.product_category_name, op.payment_type
),
MostCommonPaymentTypePerCategory AS (
    SELECT 
        product_category_name, 
        payment_type, 
        MAX(payment_count) AS max_payment_count
    FROM 
        PaymentCategory
    GROUP BY 
        product_category_name
),
TopCategories AS (
    SELECT 
        pc.product_category_name, 
        pc.payment_type, 
        pc.payment_count
    FROM 
        PaymentCategory pc
    JOIN 
        MostCommonPaymentTypePerCategory mcp 
    ON 
        pc.product_category_name = mcp.product_category_name 
        AND pc.payment_type = mcp.payment_type 
        AND pc.payment_count = mcp.max_payment_count
)
SELECT 
    product_category_name, 
    payment_type, 
    payment_count
FROM 
    TopCategories
ORDER BY 
    payment_count DESC
LIMIT 3;