SELECT MAX(distance) AS longest_distance
FROM (
  SELECT f.flight_id,
         6371 * 2 * ASIN(SQRT(
           POWER(SIN((RADIANS(Y(a2.coordinates)) - RADIANS(Y(a1.coordinates))) / 2), 2) +
           COS(RADIANS(Y(a1.coordinates))) * COS(RADIANS(Y(a2.coordinates))) *
           POWER(SIN((RADIANS(X(a2.coordinates)) - RADIANS(X(a1.coordinates))) / 2), 2)
         )) AS distance
  FROM flights f
  JOIN airports_data a1 ON f.departure_airport = a1.airport_code
  JOIN airports_data a2 ON f.arrival_airport = a2.airport_code
  WHERE json_extract(a1.city, '$.en') = 'Abakan' OR json_extract(a2.city, '$.en') = 'Abakan'
) AS distances