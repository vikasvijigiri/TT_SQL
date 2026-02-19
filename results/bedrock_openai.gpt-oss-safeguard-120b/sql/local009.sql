WITH abakan_airports AS (
    SELECT airport_code, coordinates
    FROM airports_data
    WHERE LOWER(city) = 'abakan'
), flight_distances AS (
    SELECT 
        6371 * 2 * ATAN2(
            SQRT(
                POWER(SIN(((CAST(substr(arr.coordinates, 1, instr(arr.coordinates, ',')-1) AS REAL) - CAST(substr(dep.coordinates, 1, instr(dep.coordinates, ',')-1) AS REAL)) * (3.141592653589793/180.0))/2), 2) +
                COS(CAST(substr(dep.coordinates, 1, instr(dep.coordinates, ',')-1) AS REAL) * (3.141592653589793/180.0)) *
                COS(CAST(substr(arr.coordinates, 1, instr(arr.coordinates, ',')-1) AS REAL) * (3.141592653589793/180.0)) *
                POWER(SIN(((CAST(substr(arr.coordinates, instr(arr.coordinates, ',')+1) AS REAL) - CAST(substr(dep.coordinates, instr(dep.coordinates, ',')+1) AS REAL)) * (3.141592653589793/180.0))/2), 2)
            ),
            SQRT(1 - (
                POWER(SIN(((CAST(substr(arr.coordinates, 1, instr(arr.coordinates, ',')-1) AS REAL) - CAST(substr(dep.coordinates, 1, instr(dep.coordinates, ',')-1) AS REAL)) * (3.141592653589793/180.0))/2), 2) +
                COS(CAST(substr(dep.coordinates, 1, instr(dep.coordinates, ',')-1) AS REAL) * (3.141592653589793/180.0)) *
                COS(CAST(substr(arr.coordinates, 1, instr(arr.coordinates, ',')-1) AS REAL) * (3.141592653589793/180.0)) *
                POWER(SIN(((CAST(substr(arr.coordinates, instr(arr.coordinates, ',')+1) AS REAL) - CAST(substr(dep.coordinates, instr(dep.coordinates, ',')+1) AS REAL)) * (3.141592653589793/180.0))/2), 2)
            ))
        ) AS distance_km
    FROM flights f
    JOIN airports_data dep ON f.departure_airport = dep.airport_code
    JOIN airports_data arr ON f.arrival_airport = arr.airport_code
    WHERE (f.departure_airport IN (SELECT airport_code FROM abakan_airports)
           OR f.arrival_airport IN (SELECT airport_code FROM abakan_airports))
      AND dep.coordinates IS NOT NULL
      AND arr.coordinates IS NOT NULL
)
SELECT MAX(distance_km) AS max_route_distance_km
FROM flight_distances;