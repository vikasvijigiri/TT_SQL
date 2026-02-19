WITH filtered_films AS (
    SELECT f.film_id
    FROM film f
    JOIN language l ON f.language_id = l.language_id
    JOIN film_category fc ON f.film_id = fc.film_id
    JOIN category c ON fc.category_id = c.category_id
    WHERE LOWER(l.name) = 'english'
      AND LOWER(c.name) = 'children'
      AND LOWER(f.rating) IN ('g', 'pg')
      AND f.length <= 120
      AND f.release_year BETWEEN 2000 AND 2010
)
SELECT a.first_name || ' ' || a.last_name AS full_name
FROM filtered_films ff
JOIN film_actor fa ON ff.film_id = fa.film_id
JOIN actor a ON fa.actor_id = a.actor_id
GROUP BY a.actor_id
ORDER BY COUNT(*) DESC
LIMIT 1;