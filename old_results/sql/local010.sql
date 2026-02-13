WITH city_pairs AS (
    SELECT 
        CASE WHEN ad1.city < ad2.city THEN ad1.city ELSE ad2.city END AS city1, 
        CASE WHEN ad1.city < ad2.city THEN ad2.city ELSE ad1.city END AS city2, 
        AVG(
            2 * 6371 * ASIN(SQRT(
                POWER(SIN((RADIANS(Y(ad2.coordinates)) - RADIANS(Y(ad1.coordinates))) / 2), 2) +
                COS(RADIANS(Y(ad1.coordinates))) * COS(RADIANS(Y(ad2.coordinates))) *
                POWER(SIN((RADIANS(X(ad2.coordinates)) - RADIANS(X(ad1.coordinates))) / 2), 2)
            ))
        ) AS avg_distance
    FROM flights f
    JOIN airports_data ad1 ON f.departure_airport = ad1.airport_code
    JOIN airports_data ad2 ON f.arrival_airport = ad2.airport_code
    GROUP BY city1, city2
),
categorized_pairs AS (
    SELECT 
        city1, 
        city2, 
        avg_distance,
        CASE 
            WHEN avg_distance < 1000 THEN '0-999'
            WHEN avg_distance < 2000 THEN '1000-1999'
            WHEN avg_distance < 3000 THEN '2000-2999'
            WHEN avg_distance < 4000 THEN '3000-3999'
            WHEN avg_distance < 5000 THEN '4000-4999'
            WHEN avg_distance < 6000 THEN '5000-5999'
            ELSE '6000+'
        END AS distance_range
    FROM city_pairs
),
range_counts AS (
    SELECT 
        distance_range, 
        COUNT(*) AS pair_count
    FROM categorized_pairs
    GROUP BY distance_range
)
SELECT 
    distance_range, 
    pair_count
FROM range_counts
ORDER BY pair_count ASC
LIMIT 1;