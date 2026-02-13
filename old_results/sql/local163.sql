/*  Goal:  For each faculty rank, return the faculty member(s) whose salary is
    closest to the average salary of that rank (i.e., the smallest absolute
    salary difference).  The query now uses the correct table and column names. */
WITH avg_by_rank AS (
    SELECT 
        FacRank,
        AVG(FacSalary) AS avg_salary
    FROM university_faculty
    GROUP BY FacRank
),
salary_diff AS (
    SELECT 
        uf.FacNo,
        uf.FacFirstName,
        uf.FacLastName,
        uf.FacRank,
        uf.FacSalary,
        ABS(uf.FacSalary - a.avg_salary) AS diff_to_avg
    FROM university_faculty uf
    JOIN avg_by_rank a
          ON uf.FacRank = a.FacRank
),
min_diff_per_rank AS (
    SELECT 
        FacRank,
        MIN(diff_to_avg) AS min_diff
    FROM salary_diff
    GROUP BY FacRank
)
SELECT 
    d.FacRank,
    d.FacFirstName,
    d.FacLastName,
    d.FacSalary
FROM salary_diff d
JOIN min_diff_per_rank m
      ON d.FacRank = m.FacRank
     AND d.diff_to_avg = m.min_diff
ORDER BY d.FacRank;