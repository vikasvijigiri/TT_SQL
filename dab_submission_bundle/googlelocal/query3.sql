WITH "parsed_hours" AS (
  SELECT bd.gmap_id,
         bd.name,
         bd.hours,
         json_extract(je.value, '$[0]') AS day,
         json_extract(je.value, '$[1]') AS time_range,
         CASE
           WHEN json_extract(je.value, '$[1]') LIKE '%Open 24 hours%' THEN 24
           WHEN json_extract(je.value, '$[1]') LIKE '%Closed%' THEN NULL
           ELSE
             CASE
               WHEN regexp_extract(json_extract(je.value, '$[1]'), '([0-9]{1,2})(?::[0-9]{2})?([AP]M)$', 2) = 'PM' THEN
                 CASE
                   WHEN CAST(regexp_extract(json_extract(je.value, '$[1]'), '([0-9]{1,2})(?::[0-9]{2})?([AP]M)$', 1) AS INTEGER) = 12 THEN 12
                   ELSE CAST(regexp_extract(json_extract(je.value, '$[1]'), '([0-9]{1,2})(?::[0-9]{2})?([AP]M)$', 1) AS INTEGER) + 12
                 END
               WHEN regexp_extract(json_extract(je.value, '$[1]'), '([0-9]{1,2})(?::[0-9]{2})?([AP]M)$', 2) = 'AM' THEN
                 CAST(regexp_extract(json_extract(je.value, '$[1]'), '([0-9]{1,2})(?::[0-9]{2})?([AP]M)$', 1) AS INTEGER)
               ELSE NULL
             END
         END AS close_hour_24
  FROM "business_description" bd
  JOIN json_each(bd.hours) je
  WHERE bd.hours IS NOT NULL AND bd.hours != 'nan'
),
"open_businesses" AS (
  SELECT DISTINCT gmap_id, name, hours
  FROM "parsed_hours"
  WHERE day IN ('Monday','Tuesday','Wednesday','Thursday','Friday')
    AND close_hour_24 >= 18
)
SELECT ob.name,
       ob.hours,
       ROUND(COALESCE(AVG(r.rating), 0), 2) AS avg_rating
FROM "open_businesses" ob
JOIN "review" r ON ob.gmap_id = r.gmap_id
GROUP BY ob.name, ob.hours
ORDER BY avg_rating DESC, ob.name ASC
LIMIT 5;