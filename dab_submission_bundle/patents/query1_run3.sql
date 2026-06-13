WITH raw_cpc AS (
    SELECT json_extract(je.value, '$.code') AS cpc_code,
           CAST(regexp_extract(p.filing_date, '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) AS year
    FROM "publicationinfo" p
    CROSS JOIN json_each(p.cpc) je
    WHERE p.cpc IS NOT NULL
      AND p.filing_date IS NOT NULL
      AND json_extract(je.value, '$.code') IS NOT NULL
),
yearly_counts AS (
    SELECT cpc_code, year, COUNT(*) AS filings
    FROM raw_cpc
    GROUP BY cpc_code, year
),
filtered_counts AS (
    SELECT yc.cpc_code, yc.year, yc.filings
    FROM yearly_counts yc
    JOIN "cpc_definition" d ON yc.cpc_code = d.symbol
    WHERE d.level = 5
),
ema_calc AS (
    SELECT fc.cpc_code,
           fc.year,
           CAST(fc.filings AS REAL) AS ema
    FROM filtered_counts fc
    WHERE fc.year = (
        SELECT MIN(year)
        FROM filtered_counts f2
        WHERE f2.cpc_code = fc.cpc_code
    )
    UNION ALL
    SELECT fc.cpc_code,
           fc.year,
           0.2 * fc.filings + 0.8 * e.ema
    FROM ema_calc e
    JOIN filtered_counts fc ON fc.cpc_code = e.cpc_code AND fc.year = e.year + 1
),
max_ema_per_code AS (
    SELECT cpc_code, MAX(ema) AS max_ema
    FROM ema_calc
    GROUP BY cpc_code
),
best_year AS (
    SELECT e.cpc_code,
           e.year AS best_year,
           e.ema AS max_ema
    FROM ema_calc e
    JOIN max_ema_per_code m ON e.cpc_code = m.cpc_code AND e.ema = m.max_ema
    WHERE e.year = 2022
)
SELECT b.cpc_code,
       b.max_ema
FROM best_year b
ORDER BY b.max_ema DESC;