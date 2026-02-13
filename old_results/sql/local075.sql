WITH valid_products AS (
    SELECT product_id
    FROM shopping_cart_page_hierarchy
    WHERE page_id NOT IN (1, 2, 12, 13)
),
product_events AS (
    SELECT p.product_id,
           SUM(CASE WHEN e.event_type = 1 THEN 1 ELSE 0 END) AS views,
           SUM(CASE WHEN e.event_type = 2 THEN 1 ELSE 0 END) AS added_to_cart,
           SUM(CASE WHEN e.event_type = 3 THEN 1 ELSE 0 END) AS left_in_cart
    FROM shopping_cart_events e
    JOIN shopping_cart_page_hierarchy p ON e.page_id = p.page_id
    WHERE p.product_id IN (SELECT product_id FROM valid_products)
    GROUP BY p.product_id
),
product_purchases AS (
    SELECT vp.product_id,
           COUNT(*) AS purchases
    FROM valid_products vp
    JOIN shopping_cart_page_hierarchy p ON vp.product_id = p.product_id
    JOIN shopping_cart_events e ON p.page_id = e.page_id
    JOIN customer_transactions t ON e.cookie_id = t.customer_id
    WHERE t.txn_type = 'purchase'
    GROUP BY vp.product_id
)
SELECT e.product_id,
       e.views,
       e.added_to_cart,
       e.left_in_cart,
       COALESCE(p.purchases, 0) AS purchases
FROM product_events e
LEFT JOIN product_purchases p ON e.product_id = p.product_id;