WITH parsed_trade AS (
    SELECT
        "Index" AS idx,
        COALESCE(
            TRY_CAST("Date" AS TIMESTAMP),
            TRY_STRPTIME("Date", '%B %d, %Y'),
            TRY_STRPTIME("Date", '%d %b %Y'),
            TRY_STRPTIME("Date", '%Y-%m-%d %H:%M:%S')
        ) AS ts,
        "CloseUSD"::DOUBLE AS close_usd
    FROM "index_trade"
    WHERE COALESCE(
            TRY_CAST("Date" AS TIMESTAMP),
            TRY_STRPTIME("Date", '%B %d, %Y'),
            TRY_STRPTIME("Date", '%d %b %Y'),
            TRY_STRPTIME("Date", '%Y-%m-%d %H:%M:%S')
        ) >= DATE '2000-01-01'
),
month_end_price AS (
    SELECT
        idx,
        DATE_TRUNC('month', ts)::DATE AS month,
        close_usd AS month_close,
        ROW_NUMBER() OVER (PARTITION BY idx, DATE_TRUNC('month', ts)::DATE ORDER BY ts DESC) AS rn
    FROM parsed_trade
),
monthly_shares AS (
    SELECT
        idx,
        month_close,
        1.0 / NULLIF(month_close, 0) AS shares
    FROM month_end_price
    WHERE rn = 1
),
latest_price AS (
    SELECT
        idx,
        close_usd AS latest_close,
        ROW_NUMBER() OVER (PARTITION BY idx ORDER BY ts DESC) AS rn
    FROM parsed_trade
),
agg_returns AS (
    SELECT
        ms.idx,
        lp.latest_close,
        SUM(ms.shares) AS total_shares,
        COUNT(*) AS months_invested,
        (lp.latest_close * SUM(ms.shares)) / NULLIF(COUNT(*), 0) AS overall_return_factor
    FROM monthly_shares ms
    JOIN latest_price lp ON lp.idx = ms.idx AND lp.rn = 1
    GROUP BY ms.idx, lp.latest_close
),
index_country_map AS (
    SELECT * FROM (VALUES
        ('HSI', 'Hong Kong'),
        ('N225', 'Japan'),
        ('IXIC', 'United States'),
        ('GDAXI', 'Germany'),
        ('GSPTSE', 'Canada'),
        ('NSEI', 'India'),
        ('TWII', 'Taiwan'),
        ('000001.SS', 'China'),
        ('J203.JO', 'South Africa'),
        ('SSMI', 'Switzerland'),
        ('399001.SZ', 'China'),
        ('N100', 'United States')
    ) AS t(idx, country)
)
SELECT
    ar.idx AS "Index",
    ar.overall_return_factor AS return_factor,
    icm.country
FROM agg_returns ar
JOIN index_country_map icm ON icm.idx = ar.idx
ORDER BY ar.overall_return_factor DESC
LIMIT 5;