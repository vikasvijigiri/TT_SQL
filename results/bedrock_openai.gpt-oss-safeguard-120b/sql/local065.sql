WITH target_pizzas AS (
    SELECT pizza_id, LOWER(pizza_name) AS name
    FROM pizza_names
    WHERE LOWER(pizza_name) IN ('meat lovers', 'vegetarian')
)
SELECT COALESCE(SUM(
    CASE 
        WHEN LOWER(tp.name) = 'meat lovers' THEN 12
        WHEN LOWER(tp.name) = 'vegetarian' THEN 10
        ELSE 0
    END
    + COALESCE(pge.extras_count, 0) * 1
), 0) AS total_income
FROM pizza_customer_orders pco
JOIN target_pizzas tp ON pco.pizza_id = tp.pizza_id
JOIN pizza_runner_orders pro ON pco.order_id = pro.order_id
LEFT JOIN pizza_get_extras pge ON pco.order_id = pge.order_id
WHERE pro.cancellation = 0;