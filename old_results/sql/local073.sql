WITH StandardToppings AS (
  SELECT o.order_id, o.customer_id, o.pizza_id, pn.pizza_name, 
         t.topping_name
  FROM pizza_customer_orders o
  JOIN pizza_names pn ON o.pizza_id = pn.pizza_id
  JOIN pizza_recipes pr ON o.pizza_id = pr.pizza_id
  JOIN pizza_toppings t ON ',' || pr.toppings || ',' LIKE '%,' || t.topping_id || ',%'
),
ExcludedToppings AS (
  SELECT o.order_id, t.topping_name
  FROM pizza_customer_orders o
  JOIN pizza_get_exclusions pe ON o.order_id = pe.order_id
  JOIN pizza_toppings t ON ',' || pe.exclusions || ',' LIKE '%,' || t.topping_id || ',%'
),
ExtraToppings AS (
  SELECT o.order_id, t.topping_name
  FROM pizza_customer_orders o
  JOIN pizza_get_extras px ON o.order_id = px.order_id
  JOIN pizza_toppings t ON ',' || px.extras || ',' LIKE '%,' || t.topping_id || ',%'
),
FinalToppings AS (
  SELECT st.order_id, st.customer_id, st.pizza_id, st.pizza_name,
         CASE WHEN COUNT(*) > 1 THEN '2x' || st.topping_name ELSE st.topping_name END AS topping_name
  FROM (
    SELECT st.order_id, st.customer_id, st.pizza_id, st.pizza_name, st.topping_name
    FROM StandardToppings st
    LEFT JOIN ExcludedToppings et ON st.order_id = et.order_id AND st.topping_name = et.topping_name
    WHERE et.topping_name IS NULL
    UNION ALL
    SELECT xt.order_id, xt.customer_id, xt.pizza_id, xt.pizza_name, xt.topping_name
    FROM ExtraToppings xt
  ) AS st
  GROUP BY st.order_id, st.customer_id, st.pizza_id, st.pizza_name, st.topping_name
),
PizzaIDAssignment AS (
  SELECT ft.order_id, ft.customer_id, ft.pizza_name, 
         CASE WHEN ft.pizza_name = 'Meatlovers' THEN 1 ELSE 2 END AS pizza_id,
         ft.topping_name
  FROM FinalToppings ft
)
SELECT pia.order_id, pia.customer_id, pia.pizza_name, pia.pizza_id,
       (pia.pizza_name || ': ' || GROUP_CONCAT(pia.topping_name ORDER BY pia.topping_name)) AS final_ingredients
FROM PizzaIDAssignment pia
GROUP BY pia.order_id, pia.customer_id, pia.pizza_name, pia.pizza_id
ORDER BY pia.order_id ASC;