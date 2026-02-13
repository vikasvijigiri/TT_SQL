WITH film_revenue AS (
    SELECT f.film_id, f.title, SUM(p.amount) AS total_revenue
    FROM film f
    JOIN inventory i ON i.film_id = f.film_id
    JOIN rental r ON r.inventory_id = i.inventory_id
    JOIN payment p ON p.rental_id = r.rental_id
    GROUP BY f.film_id, f.title
),
film_actor_counts AS (
    SELECT fa.film_id, COUNT(DISTINCT fa.actor_id) AS actor_count
    FROM film_actor fa
    GROUP BY fa.film_id
),
actor_film_share AS (
    SELECT fa.actor_id,
           fr.film_id,
           fr.title,
           fr.total_revenue,
           fr.total_revenue / CAST(fac.actor_count AS REAL) AS actor_share
    FROM film_actor fa
    JOIN film_revenue fr ON fr.film_id = fa.film_id
    JOIN film_actor_counts fac ON fac.film_id = fa.film_id
),
ranked_films AS (
    SELECT afs.*, ROW_NUMBER() OVER (PARTITION BY afs.actor_id ORDER BY afs.total_revenue DESC) AS rn
    FROM actor_film_share afs
),
top3 AS (
    SELECT *
    FROM ranked_films
    WHERE rn <= 3
),
avg_share AS (
    SELECT actor_id, AVG(actor_share) AS avg_actor_share
    FROM top3
    GROUP BY actor_id
)
SELECT t.actor_id,
       a.first_name,
       a.last_name,
       t.film_id,
       t.title,
       t.total_revenue,
       t.actor_share,
       av.avg_actor_share
FROM top3 t
JOIN actor a ON a.actor_id = t.actor_id
JOIN avg_share av ON av.actor_id = t.actor_id
ORDER BY t.actor_id, t.rn;