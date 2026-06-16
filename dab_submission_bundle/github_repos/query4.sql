WITH "main_langs" AS (
    SELECT "repo_name",
           LOWER(REGEXP_EXTRACT("language_description", '(?:includes:\s*|mainly written in\s*|code is in\s*|built in\s*)([A-Za-z][A-Za-z+# ]*?)(?:\s*\()', 1)) AS "main_lang"
    FROM "languages"
),
"commit_counts" AS (
    SELECT "repo_name", COUNT(*) AS "commit_cnt"
    FROM "commits"
    GROUP BY "repo_name"
)
SELECT cc."repo_name"
FROM "commit_counts" cc
JOIN "main_langs" ml ON cc."repo_name" = ml."repo_name"
WHERE ml."main_lang" IS NOT NULL
  AND ml."main_lang" <> 'python'
ORDER BY cc."commit_cnt" DESC, cc."repo_name"
LIMIT 5;