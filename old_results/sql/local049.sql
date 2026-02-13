WITH CombinedData AS (
    SELECT cd.company_id, ci.industry, CAST(strftime('%Y', cd.date_joined) AS INTEGER) AS year
    FROM companies_dates cd
    JOIN companies_industries ci ON cd.company_id = ci.company_id
),
FilteredData AS (
    SELECT company_id, industry, year
    FROM CombinedData
    WHERE year BETWEEN 2019 AND 2021
),
IndustryCounts AS (
    SELECT industry, COUNT(company_id) AS company_count
    FROM FilteredData
    GROUP BY industry
),
MaxIndustryCount AS (
    SELECT MAX(company_count) AS max_count
    FROM IndustryCounts
),
TopIndustries AS (
    SELECT ic.industry
    FROM IndustryCounts ic
    JOIN MaxIndustryCount mic ON ic.company_count = mic.max_count
),
TopIndustryData AS (
    SELECT fd.year, COUNT(fd.company_id) AS new_companies
    FROM FilteredData fd
    JOIN TopIndustries ti ON fd.industry = ti.industry
    GROUP BY fd.year
)
SELECT CASE WHEN COUNT(*) > 0 THEN AVG(CAST(new_companies AS REAL)) ELSE 0 END AS average_new_companies_per_year
FROM TopIndustryData;