WITH cleaned AS (
  SELECT
    CompanyName,
    Location,
    CAST(REPLACE(REPLACE(REPLACE(REPLACE(Salary, '$', ''), ',', ''), ' ', ''), '₹', '') AS REAL) AS salary_num
  FROM SalaryDataset
  WHERE Location IN ('Mumbai', 'Pune', 'New Delhi', 'Hyderabad')
    AND Salary IS NOT NULL
),
city_avg AS (
  SELECT
    Location,
    CompanyName,
    AVG(salary_num) AS avg_city_salary
  FROM cleaned
  GROUP BY Location, CompanyName
),
national_avg AS (
  SELECT AVG(CAST(REPLACE(REPLACE(REPLACE(REPLACE(Salary, '$', ''), ',', ''), ' ', ''), '₹', '') AS REAL)) AS avg_national_salary
  FROM SalaryDataset
  WHERE Salary IS NOT NULL
),
ranked AS (
  SELECT
    ca.Location,
    ca.CompanyName,
    ca.avg_city_salary,
    na.avg_national_salary,
    ROW_NUMBER() OVER (PARTITION BY ca.Location ORDER BY ca.avg_city_salary DESC) AS rn
  FROM city_avg ca
  CROSS JOIN national_avg na
)
SELECT
  Location,
  CompanyName,
  avg_city_salary AS "Average Salary in State",
  avg_national_salary AS "Average Salary in Country"
FROM ranked
WHERE rn <= 5
ORDER BY Location, avg_city_salary DESC;