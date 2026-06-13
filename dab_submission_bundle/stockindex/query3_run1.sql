WITH parsed_trade AS (
    SELECT
        "Index",
        TRY_CAST("Date" AS TIMESTAMP) AS ts,
        "CloseUSD"
    FROM "index_trade"
    WHERE TRY_CAST("Date" AS TIMESTAMP) >= DATE '2000-01-01'
),
monthly_end AS (
    SELECT
        "Index",
        DATE_TRUNC('month', ts)::DATE AS month,
        "CloseUSD" AS month_close,
        ROW_NUMBER() OVER (PARTITION BY "Index", DATE_TRUNC('month', ts)::DATE ORDER BY ts DESC) AS rn
    FROM parsed_trade
),
monthly_contributions AS (
    SELECT
        "Index",
        1.0 / month_close AS shares
    FROM monthly_end
    WHERE rn = 1
),
latest_price AS (
    SELECT
        "Index",
        "CloseUSD" AS latest_close
    FROM (
        SELECT
            "Index",
            "CloseUSD",
            ROW_NUMBER() OVER (PARTITION BY "Index" ORDER BY ts DESC) AS rn
        FROM parsed_trade
    ) lp
    WHERE rn = 1
),
agg AS (
    SELECT
        mc."Index",
        lp.latest_close * SUM(mc.shares) AS final_value,
        COUNT(*) AS months_invested,
        (lp.latest_close * SUM(mc.shares)) / NULLIF(COUNT(*), 0) AS overall_return_factor
    FROM monthly_contributions mc
    JOIN latest_price lp ON lp."Index" = mc."Index"
    GROUP BY mc."Index", lp.latest_close
)
SELECT
    a."Index",
    a.overall_return_factor
FROM agg a
ORDER BY a.overall_return_factor DESC
LIMIT 5;