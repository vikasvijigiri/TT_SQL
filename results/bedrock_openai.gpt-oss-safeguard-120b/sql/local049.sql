WITH unicorn_companies AS (
    SELECT cf.company_id,
           MIN(CAST(strftime('%Y', cd.date_joined) AS INTEGER)) AS unicorn_year
    FROM companies_funding cf
    JOIN companies_dates cd ON cf.company_id = cd.company_id
    WHERE cf.valuation >= 1000000000
    GROUP BY cf.company_id
    HAVING MIN(CAST(strftime('%Y', cd.date_joined) AS INTEGER)) BETWEEN 2019 AND 2021
),
unicorns_by_year AS (
    SELECT uc.company_id,
           uc.unicorn_year,
           ci.industry
    FROM unicorn_companies uc
    JOIN companies_industries ci ON uc.company_id = ci.company_id
),
yearly_counts AS (
    SELECT industry,
           unicorn_year,
           COUNT(DISTINCT company_id) AS unicorns_per_year
    FROM unicorns_by_year
    GROUP BY industry, unicorn_year
),
industry_totals AS (
    SELECT industry,
           SUM(unicorns_per_year) AS total_unicorns
    FROM yearly_counts
    GROUP BY industry
)
SELECT industry AS top_industry,
       CAST(total_unicorns AS REAL) / 3 AS average_unicorns_per_year
FROM industry_totals
ORDER BY total_unicorns DESC
LIMIT 1;