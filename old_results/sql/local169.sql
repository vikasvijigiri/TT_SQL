WITH base AS (
    SELECT b.id_bioguide,
           b.full_name,
           printf('%04d-12-31', CAST(strftime('%Y', b.first_term_start) AS INTEGER) + n) AS reference_date
    FROM (
        SELECT l.id_bioguide,
               l.full_name,
               ft.first_term_start
        FROM legislators l
        JOIN (
            SELECT id_bioguide,
                   MIN(term_start) AS first_term_start
            FROM legislators_terms
            GROUP BY id_bioguide
        ) ft ON l.id_bioguide = ft.id_bioguide
        WHERE ft.first_term_start >= '1917-01-01'
          AND ft.first_term_start <= '1999-12-31'
    ) b
    JOIN (
        SELECT 1 AS n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12 UNION ALL SELECT 13 UNION ALL SELECT 14 UNION ALL SELECT 15 UNION ALL SELECT 16 UNION ALL SELECT 17 UNION ALL SELECT 18 UNION ALL SELECT 19 UNION ALL SELECT 20
    ) nums ON 1 = 1
)
SELECT b.id_bioguide,
       b.full_name,
       b.reference_date,
       CASE WHEN EXISTS (
           SELECT 1 FROM legislators_terms lt
           WHERE lt.id_bioguide = b.id_bioguide
             AND (lt.term_end IS NULL OR lt.term_end > b.reference_date)
       ) THEN 1 ELSE 0 END AS still_in_office
FROM base b
ORDER BY b.id_bioguide, b.reference_date;