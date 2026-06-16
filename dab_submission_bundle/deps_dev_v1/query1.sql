WITH "latest_pkg" AS (
    SELECT "Name", "Version",
           ROW_NUMBER() OVER (PARTITION BY "Name" ORDER BY "UpstreamPublishedAt" DESC) AS rn
    FROM "package_query_db"."packageinfo"
    WHERE "System" = 'NPM'
),
"latest" AS (
    SELECT "Name", "Version"
    FROM "latest_pkg"
    WHERE rn = 1
),
"joined" AS (
    SELECT l."Name", l."Version", pv."ProjectName"
    FROM "latest" l
    JOIN "project_packageversion" pv
      ON pv."Name" = l."Name"
     AND pv."Version" = l."Version"
     AND pv."System" = 'NPM'
),
"proj_extracted" AS (
    SELECT "Project_Information",
           regexp_extract("Project_Information", 'The project ([^ ]+)', 1) AS proj_name,
           TRY_CAST(REPLACE(COALESCE(NULLIF(regexp_extract("Project_Information", '([0-9]+) stars', 1), ''),
                                   NULLIF(regexp_extract("Project_Information", 'stars count of ([0-9]+)', 1), ''),
                                   NULLIF(regexp_extract("Project_Information", 'total of ([0-9]+) stars', 1), ''),
                                   ''), ',', '') AS INTEGER) AS stars
    FROM "project_info"
),
"starred" AS (
    SELECT j."Name", j."Version", e.stars
    FROM "joined" j
    JOIN "proj_extracted" e
      ON e.proj_name = j."ProjectName"
    WHERE e.stars IS NOT NULL
)
SELECT "Name", "Version", stars
FROM "starred"
ORDER BY stars DESC, "Name"
LIMIT 5;