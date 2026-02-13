WITH first_state AS (
    SELECT lt.id_bioguide,
           lt.state AS first_state
    FROM legislators_terms lt
    WHERE lt.term_start = (
        SELECT MIN(term_start)
        FROM legislators_terms lt2
        WHERE lt2.id_bioguide = lt.id_bioguide
    )
), qualifying AS (
    SELECT DISTINCT lt.id_bioguide
    FROM legislators_terms lt
    WHERE date(lt.term_start, 'start of year', '+1 year', '-1 day') <= lt.term_end
)
SELECT fs.first_state AS state_abbr,
       COUNT(*) AS count
FROM first_state fs
JOIN legislators l ON l.id_bioguide = fs.id_bioguide
JOIN qualifying q ON q.id_bioguide = l.id_bioguide
WHERE l.gender = 'F'
GROUP BY fs.first_state
ORDER BY count DESC
LIMIT 1;