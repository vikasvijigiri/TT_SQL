WITH BaseOrders AS (
    SELECT o.order_id, o.pizza_id, r.toppings, o.exclusions, o.extras
    FROM pizza_customer_orders o
    JOIN pizza_recipes r ON o.pizza_id = r.pizza_id
),
ParsedToppings AS (
    SELECT bo.order_id, bo.pizza_id, pt.topping_id, pt.topping_name,
           (CASE WHEN instr(',' || bo.toppings || ',', ',' || pt.topping_id || ',') > 0 THEN 1 ELSE 0 END) AS base_quantity,
           (CASE WHEN instr(',' || bo.extras || ',', ',' || pt.topping_id || ',') > 0 THEN 1 ELSE 0 END) AS extra_quantity,
           (CASE WHEN instr(',' || bo.exclusions || ',', ',' || pt.topping_id || ',') > 0 THEN 1 ELSE 0 END) AS exclusion_quantity
    FROM BaseOrders bo
    JOIN pizza_toppings pt ON instr(',' || bo.toppings || ',', ',' || pt.topping_id || ',') > 0
),
TotalToppings AS (
    SELECT pt.topping_name, SUM(pt.base_quantity + pt.extra_quantity - pt.exclusion_quantity) AS total_quantity
    FROM ParsedToppings pt
    GROUP BY pt.topping_name
)
SELECT topping_name, total_quantity
FROM TotalToppings
WHERE total_quantity > 0;