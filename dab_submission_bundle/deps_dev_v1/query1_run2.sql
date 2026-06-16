WITH "latest_pkg" AS (
  SELECT p."System",
         p."Name",
         p."Version",
         p."UpstreamPublishedAt",
         ROW_NUMBER() OVER (PARTITION BY p."Name" ORDER BY p."UpstreamPublishedAt" DESC) AS rn
  FROM "package_query_db"."packageinfo" AS p
  WHERE p."System" = 'NPM'
),
"latest_pkg_filtered" AS (
  SELECT "System", "Name", "Version"
  FROM "latest_pkg"
  WHERE rn = 1
),
"joined_proj" AS (
  SELECT lp."System",
         lp."Name",
         lp."Version",
         pv."ProjectName"
  FROM "latest_pkg_filtered" lp
  JOIN "project_packageversion" pv
    ON pv."System" = lp."System"
   AND pv."Name" = lp."Name"
   AND pv."Version" = lp."Version"
),
"star_extracted" AS (
  SELECT jp."Name",
         jp."Version",
         MAX(TRY_CAST(NULLIF(regexp_extract(pi."Project_Information", '(?i)([0-9]+)\s*star', 1), '') AS INTEGER)) AS stars
  FROM "joined_proj" jp
  JOIN "project_info" pi
    ON pi."Project_Information" ILIKE '%' || jp."ProjectName" || '%'
  WHERE regexp_extract(pi."Project_Information", '(?i)([0-9]+)\s*star', 1) != ''
  GROUP BY jp."Name", jp."Version"
),
"ranked" AS (
  SELECT "Name",
         "Version",
         stars,
         ROW_NUMBER() OVER (ORDER BY stars DESC NULLS LAST) AS rn
  FROM "star_extracted"
)
SELECT "Name" AS PackageName,
       "Version" AS PackageVersion,
       stars AS GithubStars
FROM "ranked"
WHERE rn <= 5
ORDER BY stars DESC, PackageName;
