WITH RECURSIVE
cpc_year AS (
    SELECT CAST(regexp_extract(p.filing_date, '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) AS year,
           json_extract(je.value, '$.code') AS cpc_code
    FROM "publicationinfo" p
    JOIN json_each(p.cpc) je ON 1=1
    WHERE p.filing_date IS NOT NULL
      AND p.cpc IS NOT NULL
      AND json_extract(je.value, '$.code') IS NOT NULL
),
filtered AS (
    SELECT cy.cpc_code, cy.year
    FROM cpc_year cy
    JOIN "cpc_definition" d ON cy.cpc_code = d."symbol"
    WHERE d."level" = 5
),
counts AS (
    SELECT cpc_code,
           year,
           COUNT(*) AS filings
    FROM filtered
    GROUP BY cpc_code, year
),
ema_recursive AS (
    -- Base case: earliest year for each CPC code
    SELECT c.cpc_code,
           c.year,
           CAST(c.filings AS REAL) AS ema
    FROM counts c
    WHERE c.year = (
        SELECT MIN(year) FROM counts WHERE cpc_code = c.cpc_code
    )
    UNION ALL
    -- Recursive step: compute EMA for the next year
    SELECT c.cpc_code,
           c.year,
           0.2 * c.filings + 0.8 * e.ema AS ema
    FROM ema_recursive e
    JOIN counts c ON c.cpc_code = e.cpc_code AND c.year = e.year + 1
),
best AS (
    SELECT e.cpc_code,
           e.year AS best_year,
           e.ema AS max_ema
    FROM ema_recursive e
    JOIN (
        SELECT cpc_code, MAX(ema) AS max_ema
        FROM ema_recursive
        GROUP BY cpc_code
    ) m ON e.cpc_code = m.cpc_code AND e.ema = m.max_ema
    WHERE e.year = 2022
)
SELECT best.cpc_code AS cpc_group_code,
       best.best_year,
       best.max_ema
FROM best
ORDER BY best.max_ema DESC;