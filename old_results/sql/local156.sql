WITH RegionTransactions AS (
    SELECT 
        bt.txn_date,
        bm.region AS region,
        bp.price * bt.quantity AS dollar_amount,
        bt.quantity
    FROM bitcoin_transactions bt
    JOIN bitcoin_members bm ON bt.member_id = bm.member_id
    JOIN bitcoin_prices bp ON bt.ticker = bp.ticker AND bt.txn_date = bp.market_date
    WHERE bt.ticker = 'BTC'
),
AnnualRegionData AS (
    SELECT 
        strftime('%Y', txn_date) AS year,
        region,
        SUM(dollar_amount) AS total_dollar_amount,
        SUM(quantity) AS total_quantity
    FROM RegionTransactions
    GROUP BY year, region
),
FirstYearPerRegion AS (
    SELECT 
        region,
        MIN(year) AS first_year
    FROM AnnualRegionData
    GROUP BY region
),
FilteredData AS (
    SELECT 
        ard.year,
        ard.region,
        ard.total_dollar_amount / NULLIF(CAST(ard.total_quantity AS REAL), 0) AS avg_purchase_price
    FROM AnnualRegionData ard
    JOIN FirstYearPerRegion fyr ON ard.region = fyr.region
    WHERE ard.year > fyr.first_year
),
RankedData AS (
    SELECT 
        year,
        region,
        avg_purchase_price,
        RANK() OVER (PARTITION BY year ORDER BY avg_purchase_price DESC) AS price_rank
    FROM FilteredData
),
PercentageChangeData AS (
    SELECT 
        rd.year,
        rd.region,
        rd.avg_purchase_price,
        rd.price_rank,
        CASE WHEN LAG(rd.avg_purchase_price) OVER (PARTITION BY rd.region ORDER BY rd.year) IS NULL OR LAG(rd.avg_purchase_price) OVER (PARTITION BY rd.region ORDER BY rd.year) = 0 THEN NULL
             ELSE (rd.avg_purchase_price - LAG(rd.avg_purchase_price) OVER (PARTITION BY rd.region ORDER BY rd.year)) / LAG(rd.avg_purchase_price) OVER (PARTITION BY rd.region ORDER BY rd.year) * 100
        END AS percentage_change
    FROM RankedData rd
)
SELECT 
    year,
    region,
    avg_purchase_price,
    price_rank,
    percentage_change
FROM PercentageChangeData
ORDER BY year, price_rank;