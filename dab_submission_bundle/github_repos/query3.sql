SELECT COUNT(*) AS "commit_message_count"
FROM "commits" AS c
JOIN "languages" AS l ON c."repo_name" = l."repo_name"
JOIN "licenses" AS lic ON c."repo_name" = lic."repo_name"
WHERE LOWER(l."language_description") LIKE '%shell%'
  AND lic."license" = 'apache-2.0'
  AND c."message" IS NOT NULL
  AND LENGTH(c."message") < 1000
  AND NOT (
        LOWER(c."message") LIKE 'merge%'
        OR LOWER(c."message") LIKE 'update%'
        OR LOWER(c."message") LIKE 'test%'
      );