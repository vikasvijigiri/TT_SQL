WITH CountryDays AS (
    SELECT country, COUNT(DISTINCT DATE(insert_date)) AS distinct_days
    FROM alien_data
    WHERE strftime('%Y-%m', insert_date) = '2022-01'
    GROUP BY country
    HAVING distinct_days = 9
),
ConsecutiveDays AS (
    SELECT country, DATE(insert_date) AS insert_date,
           DATE(insert_date, '-' || ROW_NUMBER() OVER (PARTITION BY country ORDER BY DATE(insert_date)) || ' days') AS grp
    FROM alien_data
    WHERE country = (SELECT country FROM CountryDays)
      AND strftime('%Y-%m', insert_date) = '2022-01'
),
LongestPeriod AS (
    SELECT country, MIN(insert_date) AS start_date, MAX(insert_date) AS end_date, COUNT(*) AS period_length
    FROM ConsecutiveDays
    GROUP BY country, grp
    ORDER BY period_length DESC
    LIMIT 1
),
CapitalCity AS (
    SELECT DISTINCT city_name
    FROM cities
    JOIN cities_countries ON cities.country_code_2 = cities_countries.country_code_2
    WHERE cities.capital = 1
      AND cities_countries.country_name = (SELECT country FROM CountryDays)
),
CapitalEntries AS (
    SELECT COUNT(*) AS capital_count
    FROM alien_data
    WHERE current_location IN (SELECT city_name FROM CapitalCity)
      AND DATE(insert_date) BETWEEN (SELECT start_date FROM LongestPeriod) AND (SELECT end_date FROM LongestPeriod)
),
TotalEntries AS (
    SELECT COUNT(*) AS total_count
    FROM alien_data
    WHERE country = (SELECT country FROM CountryDays)
      AND DATE(insert_date) BETWEEN (SELECT start_date FROM LongestPeriod) AND (SELECT end_date FROM LongestPeriod)
)
SELECT CAST(CapitalEntries.capital_count AS REAL) / CAST(TotalEntries.total_count AS REAL) AS capital_proportion
FROM CapitalEntries, TotalEntries;