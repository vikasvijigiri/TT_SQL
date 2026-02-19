WITH filtered AS (
    SELECT country_code_2, capital, insert_date
    FROM cities
    WHERE insert_date BETWEEN '2022-01-01' AND '2022-01-31'
),
country_counts AS (
    SELECT country_code_2, COUNT(DISTINCT insert_date) AS distinct_days
    FROM filtered
    GROUP BY country_code_2
    HAVING distinct_days = 9
),
target_country AS (
    SELECT cc.country_code_2, ccy.country_name
    FROM country_counts cc
    JOIN cities_countries ccy ON cc.country_code_2 = ccy.country_code_2
),
distinct_dates AS (
    SELECT DISTINCT f.insert_date
    FROM filtered f
    JOIN target_country tc ON f.country_code_2 = tc.country_code_2
),
ordered_dates AS (
    SELECT insert_date,
           ROW_NUMBER() OVER (ORDER BY insert_date) AS rn,
           julianday(insert_date) - ROW_NUMBER() OVER (ORDER BY insert_date) AS grp
    FROM distinct_dates
),
seq_groups AS (
    SELECT grp,
           MIN(insert_date) AS start_date,
           MAX(insert_date) AS end_date,
           COUNT(*) AS length
    FROM ordered_dates
    GROUP BY grp
),
longest_seq AS (
    SELECT start_date, end_date, length
    FROM seq_groups
    ORDER BY length DESC, start_date
    LIMIT 1
),
period_entries AS (
    SELECT f.capital
    FROM filtered f
    JOIN target_country tc ON f.country_code_2 = tc.country_code_2
    WHERE f.insert_date BETWEEN (SELECT start_date FROM longest_seq) AND (SELECT end_date FROM longest_seq)
),
final_counts AS (
    SELECT 
        (SELECT country_name FROM target_country) AS country_name,
        (SELECT start_date FROM longest_seq) AS start_date,
        (SELECT end_date FROM longest_seq) AS end_date,
        (SELECT length FROM longest_seq) AS period_length,
        SUM(CASE WHEN capital = 1 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS capital_proportion
    FROM period_entries
)
SELECT country_name,
       start_date,
       end_date,
       period_length,
       ROUND(capital_proportion, 4) AS capital_proportion
FROM final_counts;