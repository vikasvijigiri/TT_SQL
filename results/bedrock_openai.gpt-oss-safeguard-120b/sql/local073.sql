WITH base_orders AS (
    SELECT COALESCE(e.row_id, ex.row_id) AS row_id,
           o.order_id,
           o.customer_id,
           o.pizza_id,
           o.order_time
    FROM pizza_customer_orders o
    LEFT JOIN pizza_get_extras e ON o.order_id = e.order_id
    LEFT JOIN pizza_get_exclusions ex ON o.order_id = ex.order_id
),
standard_toppings AS (
    SELECT b.row_id,
           t.topping_name,
           1 AS src
    FROM base_orders b
    JOIN pizza_recipes r ON b.pizza_id = r.pizza_id
    JOIN pizza_toppings t ON r.toppings = t.topping_id
    WHERE NOT EXISTS (
        SELECT 1 FROM pizza_get_exclusions ex
        WHERE ex.order_id = b.order_id AND ex.exclusions = t.topping_id
    )
),
extra_toppings AS (
    SELECT b.row_id,
           t.topping_name,
           1 AS src
    FROM base_orders b
    JOIN pizza_get_extras e ON b.order_id = e.order_id
    JOIN pizza_toppings t ON e.extras = t.topping_id
    WHERE NOT EXISTS (
        SELECT 1 FROM pizza_get_exclusions ex
        WHERE ex.order_id = b.order_id AND ex.exclusions = t.topping_id
    )
),
combined_toppings AS (
    SELECT row_id,
           topping_name,
           SUM(src) AS cnt
    FROM (
        SELECT * FROM standard_toppings
        UNION ALL
        SELECT * FROM extra_toppings
    )
    GROUP BY row_id, topping_name
),
formatted_tokens AS (
    SELECT row_id,
           CASE WHEN cnt = 2 THEN '2x' || topping_name ELSE topping_name END AS token,
           cnt
    FROM combined_toppings
),
final_ingredients AS (
    SELECT b.row_id,
           b.order_id,
           b.customer_id,
           pn.pizza_name,
           pn.pizza_name || ': ' || (
               SELECT group_concat(token, ', ')
               FROM (
                   SELECT token
                   FROM formatted_tokens ft
                   WHERE ft.row_id = b.row_id
                   ORDER BY cnt DESC, token
               )
           ) AS final_ingredients
    FROM base_orders b
    JOIN pizza_names pn ON b.pizza_id = pn.pizza_id
)
SELECT row_id,
       order_id,
       customer_id,
       pizza_name,
       final_ingredients
FROM final_ingredients
ORDER BY row_id ASC;