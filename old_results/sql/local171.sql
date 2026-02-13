WITH leg_start AS (
    SELECT id_bioguide, MIN(term_start) AS start_date
    FROM legislators_terms
    GROUP BY id_bioguide
)
SELECT (CAST(strftime('%Y', 'now') AS INTEGER) - CAST(strftime('%Y', start_date) AS INTEGER)) AS elapsed_years,
       COUNT(*) AS legislator_count
FROM leg_start
GROUP BY elapsed_years
ORDER BY elapsed_years;