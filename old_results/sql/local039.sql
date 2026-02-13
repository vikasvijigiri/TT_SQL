SELECT c.name AS category_name, 
       SUM(CAST((JULIANDAY(COALESCE(r.return_date, CURRENT_TIMESTAMP)) - JULIANDAY(r.rental_date)) * 24 AS REAL)) AS total_rental_hours
FROM city ci
JOIN address a ON ci.city_id = a.city_id
JOIN store s ON a.address_id = s.address_id
JOIN inventory i ON s.store_id = i.store_id
JOIN rental r ON i.inventory_id = r.inventory_id
JOIN film f ON i.film_id = f.film_id
JOIN film_category fc ON f.film_id = fc.film_id
JOIN category c ON fc.category_id = c.category_id
WHERE (ci.city LIKE 'A%' OR ci.city LIKE '%-%')
GROUP BY c.name
ORDER BY total_rental_hours DESC
LIMIT 1;