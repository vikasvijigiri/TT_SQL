SELECT c.name AS category_name,
       SUM((julianday(r.return_date) - julianday(r.rental_date)) * 24) AS total_rental_hours
FROM city ci
JOIN address a ON a.city_id = ci.city_id
JOIN customer cu ON cu.address_id = a.address_id
JOIN rental r ON r.customer_id = cu.customer_id
JOIN inventory i ON i.inventory_id = r.inventory_id
JOIN film_category fc ON fc.film_id = i.film_id
JOIN category c ON c.category_id = fc.category_id
WHERE r.return_date IS NOT NULL
  AND (LOWER(ci.city) LIKE 'a%' OR LOWER(ci.city) LIKE '%-%')
GROUP BY c.name
ORDER BY total_rental_hours DESC
LIMIT 1;