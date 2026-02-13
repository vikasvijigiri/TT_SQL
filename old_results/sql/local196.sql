WITH earliest AS (
    SELECT p.customer_id, p.rental_id, p.payment_date
    FROM payment p
    JOIN (
        SELECT customer_id, MIN(payment_date) AS first_payment_date
        FROM payment
        GROUP BY customer_id
    ) ep ON p.customer_id = ep.customer_id AND p.payment_date = ep.first_payment_date
),
first_rating AS (
    SELECT e.customer_id, f.rating
    FROM earliest e
    JOIN rental r ON r.rental_id = e.rental_id
    JOIN inventory i ON i.inventory_id = r.inventory_id
    JOIN film f ON f.film_id = i.film_id
),
customer_spent AS (
    SELECT customer_id, SUM(amount) AS total_spent
    FROM payment
    GROUP BY customer_id
),
customer_rentals AS (
    SELECT customer_id, COUNT(*) AS total_rentals
    FROM rental
    GROUP BY customer_id
)
SELECT fr.rating,
       AVG(cs.total_spent) AS avg_total_spent,
       AVG(cr.total_rentals - 1) AS avg_subsequent_rentals
FROM first_rating fr
JOIN customer_spent cs ON cs.customer_id = fr.customer_id
JOIN customer_rentals cr ON cr.customer_id = fr.customer_id
GROUP BY fr.rating;