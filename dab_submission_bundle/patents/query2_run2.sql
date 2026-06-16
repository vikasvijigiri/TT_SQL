WITH
    filtered_patents AS (
        SELECT
            rowid AS pub_id,
            filing_date,
            grant_date,
            Patents_info,
            cpc
        FROM "publicationinfo"
        WHERE lower("Patents_info") LIKE '%germany%'
          AND lower("grant_date") LIKE '%2019%'
          AND (
                lower("grant_date") LIKE '%july%'
                OR lower("grant_date") LIKE '%august%'
                OR lower("grant_date") LIKE '%september%'
                OR lower("grant_date") LIKE '%october%'
                OR lower("grant_date") LIKE '%november%'
                OR lower("grant_date") LIKE '%december%'
          )
    ),
    cpc_mapped AS (
        SELECT
            fp.pub_id,
            fp.filing_date,
            upper(trim(fp.cpc)) AS symbol,
            cd."titleFull",
            CAST(substr(fp.filing_date, -4) AS INTEGER) AS filing_year
        FROM filtered_patents fp
        JOIN "cpc_definition" cd
          ON cd."symbol" = upper(trim(fp.cpc))
        WHERE CAST(cd."level" AS INTEGER) = 4
    ),
    yearly_counts AS (
        SELECT
            symbol,
            "titleFull",
            filing_year,
            COUNT(DISTINCT pub_id) AS filings
        FROM cpc_mapped
        GROUP BY symbol, "titleFull", filing_year
    ),
    ema_calc AS (
        SELECT
            yc.symbol,
            yc."titleFull",
            yc.filing_year,
            yc.filings,
            CAST(yc.filings AS REAL) AS ema
        FROM yearly_counts yc
        WHERE yc.filing_year = (
            SELECT MIN(yc2.filing_year)
            FROM yearly_counts yc2
            WHERE yc2.symbol = yc.symbol
        )
        UNION ALL
        SELECT
            y.symbol,
            y."titleFull",
            y.filing_year,
            y.filings,
            (0.1 * y.filings) + (0.9 * e.ema) AS ema
        FROM ema_calc e
        JOIN yearly_counts y
          ON y.symbol = e.symbol
         AND y.filing_year = e.filing_year + 1
    ),
    best_per_cpc AS (
        SELECT
            symbol,
            "titleFull",
            filing_year AS Best_Year,
            ema,
            ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY ema DESC) AS rn
        FROM ema_calc
    )
SELECT
    "titleFull" AS CPC_Title,
    symbol AS CPC_Code,
    Best_Year,
    ema AS EMA
FROM best_per_cpc
WHERE rn = 1
ORDER BY EMA DESC;