SELECT t.topping_name AS ingredient_name,
       COUNT(*) AS total_quantity_used
FROM pizza_clean_customer_orders AS co
JOIN pizza_recipes AS r ON co.pizza_id = r.pizza_id
JOIN pizza_toppings AS t ON ',' || r.toppings || ',' LIKE '%,' || t.topping_id || ',%'
GROUP BY t.topping_name
ORDER BY t.topping_name