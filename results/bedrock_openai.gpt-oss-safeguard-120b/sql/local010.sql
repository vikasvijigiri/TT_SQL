WITH pair_distances AS (
  SELECT
    CASE WHEN LOWER(a1.city) < LOWER(a2.city) THEN LOWER(a1.city) ELSE LOWER(a2.city) END AS city_a,
    CASE WHEN LOWER(a1.city) < LOWER(a2.city) THEN LOWER(a2.city) ELSE LOWER(a1.city) END AS city_b,
    6371 * acos(
      sin((CAST(substr(a1.coordinates, 1, instr(a1.coordinates, ',')-1) AS REAL) * 3.141592653589793 / 180.0)) *
      sin((CAST(substr(a2.coordinates, 1, instr(a2.coordinates, ',')-1) AS REAL) * 3.141592653589793 / 180.0)) +
      cos((CAST(substr(a1.coordinates, 1, instr(a1.coordinates, ',')-1) AS REAL) * 3.141592653589793 / 180.0)) *
      cos((CAST(substr(a2.coordinates, 1, instr(a2.coordinates, ',')-1) AS REAL) * 3.141592653589793 / 180.0)) *
      cos(((CAST(substr(a2.coordinates, instr(a2.coordinates, ',')+1) AS REAL) - CAST(substr(a1.coordinates, instr(a1.coordinates, ',')+1) AS REAL)) * 3.141592653589793 / 180.0))
    ) AS distance_km
  FROM flights f
  JOIN airports_data a1 ON f.departure_airport = a1.airport_code
  JOIN airports_data a2 ON f.arrival_airport = a2.airport_code
), avg_distances AS (
  SELECT city_a, city_b, AVG(distance_km) AS avg_distance
  FROM pair_distances
  GROUP BY city_a, city_b
), bucketed AS (
  SELECT
    CASE
      WHEN avg_distance < 1000 THEN '0-999'
      WHEN avg_distance < 2000 THEN '1000-1999'
      WHEN avg_distance < 3000 THEN '2000-2999'
      WHEN avg_distance < 4000 THEN '3000-3999'
      WHEN avg_distance < 5000 THEN '4000-4999'
      WHEN avg_distance < 6000 THEN '5000-5999'
      ELSE '6000+'
    END AS bucket,
    COUNT(*) AS pair_count
  FROM avg_distances
  GROUP BY bucket
)
SELECT MIN(pair_count) AS min_pair_count
FROM bucketed;