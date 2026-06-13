WITH filtered_business AS (
    SELECT gmap_id, name
    FROM business_description
    WHERE name IS NOT NULL
      AND TRIM(name) != ''
      AND (
          lower(description) LIKE '%los angeles, ca%'
          OR lower(description) LIKE '%los angeles, california%'
      )
),
business_ratings AS (
    SELECT fb.name,
           AVG(r.rating) AS avg_rating,
           COUNT(r.rating) AS review_count
    FROM filtered_business fb
    JOIN review r ON fb.gmap_id = r.gmap_id
    GROUP BY fb.name
)
SELECT name, avg_rating, review_count
FROM business_ratings
ORDER BY avg_rating DESC, review_count DESC
LIMIT 5