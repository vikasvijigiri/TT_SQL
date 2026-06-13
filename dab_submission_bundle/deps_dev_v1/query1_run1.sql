WITH "latest_pkg" AS (
  SELECT "Name", "Version", "UpstreamPublishedAt",
         ROW_NUMBER() OVER (PARTITION BY "Name" ORDER BY "UpstreamPublishedAt" DESC NULLS LAST) AS rn
  FROM "package_query_db"."packageinfo"
  WHERE "System" = 'NPM'
),
"latest_only" AS (
  SELECT "Name", "Version"
  FROM "latest_pkg"
  WHERE rn = 1
),
"linked" AS (
  SELECT lo."Name", lo."Version", ppv."ProjectName"
  FROM "latest_only" lo
  JOIN "project_packageversion" ppv
    ON ppv."Name" = lo."Name"
   AND ppv."Version" = lo."Version"
   AND ppv."System" = 'NPM'
),
"star_info" AS (
  SELECT l."Name", l."Version",
         COALESCE(
           TRY_CAST(REPLACE(NULLIF(regexp_extract(pi."Project_Information", '([0-9]+) stars', 1), ''), ',', '') AS INTEGER),
           TRY_CAST(REPLACE(NULLIF(regexp_extract(pi."Project_Information", 'stars count of ([0-9]+)', 1), ''), ',', '') AS INTEGER)
         ) AS stars
  FROM "linked" l
  JOIN "project_info" pi
    ON pi."Project_Information" LIKE '%' || l."ProjectName" || '%'
  WHERE pi."Project_Information" IS NOT NULL
),
"ranked" AS (
  SELECT "Name", "Version", MAX(stars) AS stars
  FROM "star_info"
  GROUP BY "Name", "Version"
)
SELECT "Name", "Version", stars
FROM "ranked"
WHERE stars IS NOT NULL
ORDER BY stars DESC, "Name"
LIMIT 5;