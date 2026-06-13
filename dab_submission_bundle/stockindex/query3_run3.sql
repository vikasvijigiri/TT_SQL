WITH parsed_dates AS (
    SELECT
        "Index" AS idx,
        COALESCE(
            TRY_STRPTIME("Date", '%Y-%m-%d %H:%M:%S'),
            TRY_STRPTIME("Date", '%B %d, %Y at %I:%M %p'),
            TRY_STRPTIME("Date", '%d %b %Y, %H:%M'),
            TRY_STRPTIME("Date", '%d %b %Y')
        ) AS ts,
        "CloseUSD" AS close_usd
    FROM "index_trade"
    WHERE COALESCE(
            TRY_STRPTIME("Date", '%Y-%m-%d %H:%M:%S'),
            TRY_STRPTIME("Date", '%B %d, %Y at %I:%M %p'),
            TRY_STRPTIME("Date", '%d %b %Y, %H:%M'),
            TRY_STRPTIME("Date", '%d %b %Y')
        ) >= DATE '2000-01-01'
),
monthly_prices AS (
    SELECT
        idx,
        DATE_TRUNC('month', ts)::DATE AS month,
        close_usd,
        ROW_NUMBER() OVER (PARTITION BY idx, DATE_TRUNC('month', ts)::DATE ORDER BY ts DESC) AS rn
    FROM parsed_dates
),
monthly_shares AS (
    SELECT
        idx,
        month,
        1.0 / NULLIF(close_usd, 0) AS shares
    FROM monthly_prices
    WHERE rn = 1
),
latest_price AS (
    SELECT
        idx,
        close_usd AS latest_close,
        ROW_NUMBER() OVER (PARTITION BY idx ORDER BY ts DESC) AS rn
    FROM parsed_dates
),
agg_returns AS (
    SELECT
        ms.idx,
        lp.latest_close,
        COUNT(*) AS months_invested,
        SUM(ms.shares) AS total_shares,
        (lp.latest_close * SUM(ms.shares)) / NULLIF(COUNT(*), 0) AS overall_return_factor
    FROM monthly_shares ms
    JOIN latest_price lp ON lp.idx = ms.idx AND lp.rn = 1
    GROUP BY ms.idx, lp.latest_close
),
index_country AS (
    SELECT * FROM (VALUES
        ('N225', 'Japan'),
        ('HSI', 'Hong Kong'),
        ('GDAXI', 'Germany'),
        ('GSPTSE', 'Canada'),
        ('NSEI', 'India'),
        ('NYA', 'United States'),
        ('IXIC', 'United States'),
        ('000001.SS', 'China'),
        ('TWII', 'Taiwan'),
        ('J203.JO', 'South Africa'),
        ('SSMI', 'Singapore'),
        ('N100', 'Netherlands'),
        ('399001.SZ', 'China')
    ) AS t(idx, country)
),
ranked AS (
    SELECT
        ar.idx,
        ar.overall_return_factor,
        ic.country,
        ROW_NUMBER() OVER (ORDER BY ar.overall_return_factor DESC) AS rn
    FROM agg_returns ar
    LEFT JOIN index_country ic ON ic.idx = ar.idx
)
SELECT
    idx AS "Index",
    overall_return_factor AS "OverallReturnFactor",
    country AS "Country"
FROM ranked
WHERE rn <= 5
ORDER BY rn;