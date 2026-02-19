WITH motorcyclist_helmets AS (
    SELECT p.case_id,
           MAX(CASE WHEN LOWER(p.party_safety_equipment_1) LIKE '%helmet%'
                     OR LOWER(p.party_safety_equipment_2) LIKE '%helmet%'
                    THEN 1 ELSE 0 END) AS helmet_worn
    FROM parties p
    WHERE LOWER(p.statewide_vehicle_type) LIKE '%motorcycle%'
    GROUP BY p.case_id
)
SELECT CASE WHEN mh.helmet_worn = 1 THEN 'Helmet Worn' ELSE 'No Helmet' END AS helmet_usage,
       (CAST(SUM(COALESCE(c.motorcyclist_killed_count, 0)) AS REAL) / COUNT(DISTINCT c.case_id) * 100.0) AS fatality_rate_percent
FROM collisions c
JOIN motorcyclist_helmets mh ON c.case_id = mh.case_id
WHERE c.motorcycle_collision = 1
GROUP BY mh.helmet_worn;