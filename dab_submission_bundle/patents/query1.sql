WITH yearly_counts AS (
    SELECT cd."symbol" AS symbol,
           CAST(regexp_extract(pi."filing_date", '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) AS year,
           COUNT(*) AS cnt
    FROM "publicationinfo" pi,
         json_each(pi."cpc") je
    JOIN "cpc_definition" cd ON cd."symbol" = json_extract(je.value, '$.code')
    WHERE json_type(pi."cpc") = 'array'
      AND cd."level" = 5
      AND pi."filing_date" IS NOT NULL
    GROUP BY cd."symbol", year
),
ordered_counts AS (
    SELECT symbol,
           year,
           cnt,
           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY year) AS rn
    FROM yearly_counts
),
ema_recursive AS (
    SELECT symbol,
           year,
           cnt,
           CAST(cnt AS REAL) AS ema,
           rn
    FROM ordered_counts
    WHERE rn = 1
    UNION ALL
    SELECT oc.symbol,
           oc.year,
           oc.cnt,
           0.2 * oc.cnt + 0.8 * er.ema AS ema,
           oc.rn
    FROM ordered_counts oc
    JOIN ema_recursive er ON oc.symbol = er.symbol AND oc.rn = er.rn + 1
),
best_ema AS (
    SELECT symbol,
           year,
           ema,
           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY ema DESC) AS rn_max
    FROM ema_recursive
)
SELECT symbol,
       year AS best_year,
       ema AS best_ema
FROM best_ema
WHERE rn_max = 1
  AND year = 2022
ORDER BY best_ema DESC;