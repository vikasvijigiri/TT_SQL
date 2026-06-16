WITH "non_python_repos" AS (
    SELECT DISTINCT "repo_name"
    FROM "languages"
    WHERE lower("language_description") NOT LIKE '%python%'
), "readme_files" AS (
    SELECT DISTINCT "sample_repo_name" AS "repo_name", "content"
    FROM "contents"
    WHERE lower("sample_path") LIKE '%readme.md%'
), "repo_flags" AS (
    SELECT np."repo_name",
           MAX(CASE WHEN lower(rf."content") LIKE '%copyright%' THEN 1 ELSE 0 END) AS "has_copyright"
    FROM "non_python_repos" np
    JOIN "readme_files" rf ON rf."repo_name" = np."repo_name"
    GROUP BY np."repo_name"
)
SELECT CAST(SUM("has_copyright") AS DOUBLE) / NULLIF(COUNT(*), 0) AS "proportion_copyright"
FROM "repo_flags";