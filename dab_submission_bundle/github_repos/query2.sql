WITH swift_repos AS (
    SELECT LOWER(l."repo_name") AS repo_name_lc
    FROM "languages" l
    WHERE LOWER(l."language_description") LIKE '%swift%'
),
joined AS (
    SELECT c."id", f."repo_name", f."path", c."repo_data_description"
    FROM "contents" c
    JOIN "files" f ON c."id" = f."id"
),
filtered AS (
    SELECT j."id",
           j."repo_name",
           j."path",
           TRY_CAST(regexp_extract(j."repo_data_description", '(\\d+)\\s+times', 1) AS INTEGER) AS copy_count
    FROM joined j
    WHERE LOWER(j."path") LIKE '%.swift'
      AND LOWER(j."repo_data_description") LIKE '%non-binary%'
      AND LOWER(j."repo_name") IN (SELECT repo_name_lc FROM swift_repos)
)
SELECT f."repo_name",
       f."id" AS file_id,
       f."path",
       f."copy_count"
FROM filtered f
ORDER BY f."copy_count" DESC NULLS LAST, f."id"
LIMIT 1;