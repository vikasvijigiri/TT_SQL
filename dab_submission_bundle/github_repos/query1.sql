WITH non_python_repos AS (
  SELECT l.repo_name
  FROM "languages" l
  WHERE lower(l.language_description) NOT LIKE '%python%'
), readme_files AS (
  SELECT f.repo_name, c.content
  FROM "files" f
  JOIN "contents" c ON c.id = f.id
  WHERE lower(f.path) LIKE '%readme.md%'
    AND f.repo_name IN (SELECT repo_name FROM non_python_repos)
), readme_flags AS (
  SELECT repo_name,
         CASE WHEN lower(content) LIKE '%copyright%' THEN 1 ELSE 0 END AS flag
  FROM readme_files
)
SELECT CAST(SUM(flag) AS DOUBLE) / NULLIF(COUNT(*), 0) AS proportion_copyright
FROM readme_flags;