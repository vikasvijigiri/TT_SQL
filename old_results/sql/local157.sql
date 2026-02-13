WITH ConvertedVolumes AS (
  SELECT 
    ticker,
    market_date,
    price,
    open,
    high,
    low,
    CASE 
      WHEN volume LIKE '%K' THEN CAST(SUBSTR(volume, 1, LENGTH(volume) - 1) AS REAL) * 1000
      WHEN volume LIKE '%M' THEN CAST(SUBSTR(volume, 1, LENGTH(volume) - 1) AS REAL) * 1000000
      WHEN volume = '-' THEN 0
      ELSE CAST(volume AS REAL)
    END AS volume
  FROM bitcoin_prices
  WHERE market_date BETWEEN '2021-08-01' AND '2021-08-10'
),
FilteredVolumes AS (
  SELECT 
    ticker,
    market_date,
    volume
  FROM ConvertedVolumes
  WHERE volume > 0
),
VolumeChanges AS (
  SELECT 
    fv1.ticker,
    fv1.market_date,
    fv1.volume AS current_volume,
    (
      SELECT fv2.volume
      FROM FilteredVolumes fv2
      WHERE fv2.ticker = fv1.ticker
        AND fv2.market_date < fv1.market_date
        AND fv2.volume > 0
      ORDER BY fv2.market_date DESC
      LIMIT 1
    ) AS previous_volume,
    CASE 
      WHEN previous_volume IS NOT NULL AND previous_volume != 0 THEN ((fv1.volume - previous_volume) / previous_volume) * 100
      ELSE NULL
    END AS percentage_change
  FROM FilteredVolumes fv1
)
SELECT 
  ticker,
  market_date,
  percentage_change
FROM VolumeChanges
ORDER BY ticker, market_date;