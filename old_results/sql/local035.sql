WITH OrderedCities AS (
  SELECT 
    geolocation_state, 
    geolocation_city, 
    geolocation_zip_code_prefix, 
    geolocation_lat, 
    geolocation_lng,
    LAG(geolocation_lat) OVER (ORDER BY geolocation_state, geolocation_city, geolocation_zip_code_prefix, geolocation_lat, geolocation_lng) AS prev_lat,
    LAG(geolocation_lng) OVER (ORDER BY geolocation_state, geolocation_city, geolocation_zip_code_prefix, geolocation_lat, geolocation_lng) AS prev_lng
  FROM olist_geolocation
),
DistanceCalculation AS (
  SELECT 
    geolocation_state, 
    geolocation_city, 
    geolocation_zip_code_prefix, 
    geolocation_lat, 
    geolocation_lng,
    prev_lat,
    prev_lng,
    6371 * 2 * ASIN(SQRT(
      POWER(SIN((geolocation_lat - prev_lat) * PI() / 180 / 2), 2) +
      COS(geolocation_lat * PI() / 180) * COS(prev_lat * PI() / 180) *
      POWER(SIN((geolocation_lng - prev_lng) * PI() / 180 / 2), 2)
    )) AS distance
  FROM OrderedCities
  WHERE prev_lat IS NOT NULL AND prev_lng IS NOT NULL
)
SELECT 
  geolocation_state, 
  geolocation_city, 
  geolocation_zip_code_prefix, 
  geolocation_lat, 
  geolocation_lng,
  prev_lat,
  prev_lng,
  distance
FROM DistanceCalculation
ORDER BY distance DESC
LIMIT 1;