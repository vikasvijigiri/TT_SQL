WITH repos_without_python AS (
    SELECT DISTINCT l1."repo_name"
    FROM "languages" l1
    WHERE NOT EXISTS (
        SELECT 1
        FROM "languages" l2
        WHERE l2."repo_name" = l1."repo_name"
          AND LOWER(l2."language_description") LIKE '%python%'
    )
),
readme_files AS (
    SELECT c."sample_repo_name", c."content"
    FROM "contents" c
    INNER JOIN repos_without_python r ON c."sample_repo_name" = r."repo_name"
    WHERE LOWER(c."sample_path") LIKE '%readme.md%'
),
readme_with_copyright AS (
    SELECT DISTINCT "sample_repo_name"
    FROM readme_files
    WHERE LOWER("content") LIKE '%copyright%'
)
SELECT COALESCE(
    COUNT(DISTINCT rc."sample_repo_name")::DOUBLE / NULLIF(COUNT(DISTINCT rf."sample_repo_name"), 0),
    0
) AS "proportion_copyright"
FROM readme_files rf
LEFT JOIN readme_with_copyright rc ON rf."sample_repo_name" = rc."sample_repo_name";