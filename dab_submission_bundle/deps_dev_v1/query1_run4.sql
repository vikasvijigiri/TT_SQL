WITH "latest_pkg" AS (
  SELECT "Name",
         "Version",
         "UpstreamPublishedAt",
         ROW_NUMBER() OVER (PARTITION BY "Name" ORDER BY "UpstreamPublishedAt" DESC) AS rn
  FROM "package_query_db"."packageinfo"
  WHERE "System" = 'NPM'
),
"latest_only" AS (
  SELECT "Name", "Version"
  FROM "latest_pkg"
  WHERE rn = 1
),
"linked" AS (
  SELECT lo."Name",
         lo."Version",
         pv."ProjectName"
  FROM "latest_only" lo
  JOIN "project_packageversion" pv
    ON pv."Name" = lo."Name"
   AND pv."Version" = lo."Version"
   AND pv."System" = 'NPM'
),
"star_info" AS (
  SELECT l."Name",
         l."Version",
         COALESCE(
           TRY_CAST(REPLACE(NULLIF(regexp_extract(pi."Project_Information", '([0-9]+) stars', 1), ''), ',', '') AS INTEGER),
           TRY_CAST(REPLACE(NULLIF(regexp_extract(pi."Project_Information", 'stars count of ([0-9]+)', 1), ''), ',', '') AS INTEGER),
           TRY_CAST(REPLACE(NULLIF(regexp_extract(pi."Project_Information", 'total of ([0-9]+) stars', 1), ''), ',', '') AS INTEGER)
         ) AS stars
  FROM "linked" l
  JOIN "project_info" pi
    ON pi."Project_Information" LIKE 'The project ' || l."ProjectName" || ' %'
   AND pi."Project_Information" LIKE '%GitHub%'
)
SELECT DISTINCT "Name", "Version", stars
FROM "star_info"
WHERE stars IS NOT NULL
ORDER BY stars DESC, "Name" ASC
LIMIT 5;