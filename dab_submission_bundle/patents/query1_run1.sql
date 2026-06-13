WITH
    cte_unnested AS (
        SELECT json_extract(je.value, '$.code') AS cpc_code,
               CAST(regexp_extract(p.filing_date, '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) AS year
        FROM "publicationinfo" p,
             json_each(p.cpc) je
        WHERE p.cpc IS NOT NULL
          AND p.filing_date IS NOT NULL
    ),
    cte_counts AS (
        SELECT cpc_code, year, COUNT(*) AS filings
        FROM cte_unnested
        GROUP BY cpc_code, year
    ),
    cte_filtered AS (
        SELECT cnt.cpc_code, cnt.year, cnt.filings
        FROM cte_counts cnt
        JOIN "cpc_definition" d ON cnt.cpc_code = d.symbol
        WHERE d.level = 5.0
    ),
    RECURSIVE cte_ema AS (
        SELECT f.cpc_code, f.year, f.filings AS ema
        FROM cte_filtered f
        JOIN (
            SELECT cpc_code, MIN(year) AS min_year
            FROM cte_filtered
            GROUP BY cpc_code
        ) m ON f.cpc_code = m.cpc_code AND f.year = m.min_year
        UNION ALL
        SELECT f.cpc_code, f.year, 0.2 * f.filings + 0.8 * e.ema AS ema
        FROM cte_ema e
        JOIN cte_filtered f ON f.cpc_code = e.cpc_code AND f.year = e.year + 1
    ),
    cte_max AS (
        SELECT cpc_code, year, ema,
               MAX(ema) OVER (PARTITION BY cpc_code) AS max_ema
        FROM cte_ema
    )
SELECT cpc_code AS cpc_group_code,
       year AS best_year,
       ema AS ema_value,
       max_ema
FROM cte_max
WHERE year = 2022
  AND ema = max_ema
ORDER BY ema DESC;