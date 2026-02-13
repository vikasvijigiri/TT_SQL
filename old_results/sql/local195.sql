WITH top_actors AS (
  SELECT fa.actor_id
  FROM rental r
  JOIN inventory i ON r.inventory_id = i.inventory_id
  JOIN film_actor fa ON i.film_id = fa.film_id
  GROUP BY fa.actor_id
  ORDER BY COUNT(*) DESC
  LIMIT 5
),
target_films AS (
  SELECT DISTINCT fa.film_id
  FROM film_actor fa
  WHERE fa.actor_id IN (SELECT actor_id FROM top_actors)
)
SELECT 
  CAST(COUNT(DISTINCT r.customer_id) AS REAL) * 100.0 / (SELECT COUNT(*) FROM customer) AS percentage
FROM rental r
JOIN inventory i ON r.inventory_id = i.inventory_id
WHERE i.film_id IN (SELECT film_id FROM target_films);