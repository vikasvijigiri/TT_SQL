WITH "non_python_repos" AS (
    SELECT DISTINCT l."repo_name"
    FROM "repo_metadata_db"."languages" AS l
    WHERE NOT EXISTS (
        SELECT 1
        FROM "repo_metadata_db"."languages" AS l2
        WHERE l2."repo_name" = l."repo_name"
          AND LOWER(l2."language_description") LIKE '%python%'
    )
), "readme_files" AS (
    SELECT c."sample_repo_name", c."content"
    FROM "contents" AS c
    WHERE LOWER(c."sample_path") LIKE '%readme.md%'
      AND c."sample_repo_name" IN (SELECT "repo_name" FROM "non_python_repos")
)
SELECT COALESCE(
    COUNT(DISTINCT CASE WHEN LOWER("content") LIKE '%copyright%' THEN "sample_repo_name" END)::DOUBLE
    / NULLIF(COUNT(DISTINCT "sample_repo_name"), 0),
    0
) AS "proportion_copyright"
FROM "readme_files";