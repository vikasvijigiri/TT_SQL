WITH "parsed_dates" AS (
  SELECT "Index",
         "Open",
         "High",
         "Low",
         COALESCE(
           TRY_STRPTIME("Date", '%d %b %Y, %H:%M'),
           TRY_STRPTIME("Date", '%B %d, %Y at %I:%M %p'),
           TRY_STRPTIME("Date", '%Y-%m-%d %H:%M:%S')
         )::DATE AS "trade_date"
  FROM "index_trade"
  WHERE "Date" IS NOT NULL
), "asian_indices" AS (
  SELECT * FROM (VALUES
    ('HSI'),
    ('N225'),
    ('000001.SS'),
    ('399001.SZ'),
    ('NSEI'),
    ('JKSE'),
    ('KOSPI'),
    ('TWII')
  ) AS v("Index")
), "volatility_agg" AS (
  SELECT p."Index",
         AVG((p."High" - p."Low") / NULLIF(p."Open", 0)) AS "avg_volatility"
  FROM "parsed_dates" p
  JOIN "asian_indices" a ON p."Index" = a."Index"
  WHERE p."trade_date" >= DATE '2020-01-01'
  GROUP BY p."Index"
)
SELECT "Index", "avg_volatility"
FROM "volatility_agg"
ORDER BY "avg_volatility" DESC
LIMIT 1;