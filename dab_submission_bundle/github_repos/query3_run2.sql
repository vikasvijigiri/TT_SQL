WITH filtered_repos AS (
    SELECT DISTINCT l."repo_name"
    FROM "repo_metadata_db"."languages" AS l
    JOIN "repo_metadata_db"."licenses" AS lic ON l."repo_name" = lic."repo_name"
    WHERE l."language_description" ILIKE '%Shell%'
      AND lic."license" = 'Apache-2.0'
)
SELECT COUNT(*) AS "commit_message_count"
FROM "commits" AS c
JOIN filtered_repos fr ON c."repo_name" = fr."repo_name"
WHERE c."message" IS NOT NULL
  AND LENGTH(c."message") < 1000
  AND NOT (
        c."message" ILIKE 'merge%'
        OR c."message" ILIKE 'update%'
        OR c."message" ILIKE 'test%'
      );