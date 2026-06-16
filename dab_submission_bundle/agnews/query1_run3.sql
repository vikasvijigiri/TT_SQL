SELECT "title"
FROM "articles"
WHERE "description" IS NOT NULL
  AND (lower("description") LIKE '%sport%' OR lower("title") LIKE '%sport%')
ORDER BY length("description") DESC
LIMIT 1