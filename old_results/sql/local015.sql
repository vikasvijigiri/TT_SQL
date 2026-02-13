SELECT 
    'Helmet Used' AS helmet_usage, 
    (SUM(c.motorcyclist_killed_count) * 100.0 / COUNT(DISTINCT c.case_id)) AS fatality_rate
FROM 
    collisions c
JOIN 
    parties p ON c.case_id = p.case_id
WHERE 
    c.motorcycle_collision = 1 AND 
    (p.party_safety_equipment_1 = 'Helmet' OR p.party_safety_equipment_2 = 'Helmet') AND
    p.party_type = 'Motorcyclist'
GROUP BY 
    helmet_usage
UNION ALL
SELECT 
    'No Helmet Used' AS helmet_usage, 
    (SUM(c.motorcyclist_killed_count) * 100.0 / COUNT(DISTINCT c.case_id)) AS fatality_rate
FROM 
    collisions c
JOIN 
    parties p ON c.case_id = p.case_id
WHERE 
    c.motorcycle_collision = 1 AND 
    (p.party_safety_equipment_1 != 'Helmet' AND p.party_safety_equipment_2 != 'Helmet') AND
    p.party_type = 'Motorcyclist'
GROUP BY 
    helmet_usage