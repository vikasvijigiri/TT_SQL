SELECT SUM(CASE 
             WHEN pn.pizza_name = 'Meat Lovers' THEN 12 + COALESCE(LENGTH(pco.extras) - LENGTH(REPLACE(pco.extras, ',', '')) + 1, 0) * 1
             WHEN pn.pizza_name = 'Vegetarian' THEN 10 + COALESCE(LENGTH(pco.extras) - LENGTH(REPLACE(pco.extras, ',', '')) + 1, 0) * 1
             ELSE 0
           END) AS total_income
FROM pizza_customer_orders pco
JOIN pizza_clean_runner_orders pcro ON pco.order_id = pcro.order_id
JOIN pizza_names pn ON pco.pizza_id = pn.pizza_id
WHERE pcro.cancellation IS NULL;