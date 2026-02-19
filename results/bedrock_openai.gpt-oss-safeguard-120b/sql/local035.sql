WITH uniq AS (
  SELECT DISTINCT geolocation_state, geolocation_city, geolocation_zip_code_prefix, geolocation_lat, geolocation_lng
  FROM olist_geolocation
),
ordered AS (
  SELECT 
    geolocation_state,
    geolocation_city,
    geolocation_zip_code_prefix,
    geolocation_lat,
    geolocation_lng,
    LAG(geolocation_state) OVER (ORDER BY geolocation_state, geolocation_city, geolocation_zip_code_prefix, geolocation_lat, geolocation_lng) AS prev_state,
    LAG(geolocation_city) OVER (ORDER BY geolocation_state, geolocation_city, geolocation_zip_code_prefix, geolocation_lat, geolocation_lng) AS prev_city,
    LAG(geolocation_zip_code_prefix) OVER (ORDER BY geolocation_state, geolocation_city, geolocation_zip_code_prefix, geolocation_lat, geolocation_lng) AS prev_zip,
    LAG(geolocation_lat) OVER (ORDER BY geolocation_state, geolocation_city, geolocation_zip_code_prefix, geolocation_lat, geolocation_lng) AS prev_lat,
    LAG(geolocation_lng) OVER (ORDER BY geolocation_state, geolocation_city, geolocation_zip_code_prefix, geolocation_lat, geolocation_lng) AS prev_lng
  FROM uniq
),
distances AS (
  SELECT 
    geolocation_state,
    geolocation_city,
    geolocation_zip_code_prefix,
    prev_state,
    prev_city,
    prev_zip,
    6371 * 2 * asin(
      sqrt(
        pow(sin(((geolocation_lat - prev_lat) * 3.141592653589793 / 180) / 2), 2) +
        cos(geolocation_lat * 3.141592653589793 / 180) *
        cos(prev_lat * 3.141592653589793 / 180) *
        pow(sin(((geolocation_lng - prev_lng) * 3.141592653589793 / 180) / 2), 2)
      )
    ) AS distance_km
  FROM ordered
  WHERE prev_lat IS NOT NULL
)
SELECT 
  prev_state,
  prev_city,
  prev_zip,
  geolocation_state,
  geolocation_city,
  geolocation_zip_code_prefix,
  distance_km AS max_distance_km
FROM distances
ORDER BY distance_km DESC
LIMIT 1;