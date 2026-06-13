WITH parsed_trade AS (
    SELECT
        "Index" AS idx,
        COALESCE(
            TRY_CAST("Date" AS TIMESTAMP),
            TRY_STRPTIME("Date", '%d %b %Y, %H:%M'),
            TRY_STRPTIME("Date", '%B %d, %Y at %I:%M %p'),
            TRY_STRPTIME("Date", '%d %b %Y'),
            TRY_STRPTIME("Date", '%Y-%m-%d %H:%M:%S')
        ) AS ts,
        "CloseUSD" AS close_usd
    FROM "index_trade"
    WHERE COALESCE(
            TRY_CAST("Date" AS TIMESTAMP),
            TRY_STRPTIME("Date", '%d %b %Y, %H:%M'),
            TRY_STRPTIME("Date", '%B %d, %Y at %I:%M %p'),
            TRY_STRPTIME("Date", '%d %b %Y'),
            TRY_STRPTIME("Date", '%Y-%m-%d %H:%M:%S')
        ) >= DATE '2000-01-01'
),
monthly_end AS (
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
    FROM monthly_end
    WHERE rn = 1
),
latest_price AS (
    SELECT
        idx,
        close_usd AS latest_close,
        ROW_NUMBER() OVER (PARTITION BY idx ORDER BY ts DESC) AS rn
    FROM parsed_trade
),
latest_price_filtered AS (
    SELECT idx, latest_close
    FROM latest_price
    WHERE rn = 1
),
agg AS (
    SELECT
        ms.idx AS "Index",
        lp.latest_close * SUM(ms.shares) AS overall_return_factor,
        COUNT(*) AS months_invested
    FROM monthly_shares ms
    JOIN latest_price_filtered lp ON lp.idx = ms.idx
    GROUP BY ms.idx, lp.latest_close
),
index_country_map AS (
    SELECT * FROM (VALUES
        ('HSI','Hong Kong'),
        ('N225','Japan'),
        ('IXIC','United States'),
        ('GDAXI','Germany'),
        ('GSPTSE','Canada'),
        ('NSEI','India'),
        ('TWII','Taiwan'),
        ('000001.SS','China'),
        ('J203.JO','South Africa'),
        ('NYA','United States')
    ) AS t(idx,country)
)
SELECT
    a."Index",
    a.overall_return_factor,
    m.country
FROM agg a
JOIN index_country_map m ON m.idx = a."Index"
ORDER BY a.overall_return_factor DESC
LIMIT 5;