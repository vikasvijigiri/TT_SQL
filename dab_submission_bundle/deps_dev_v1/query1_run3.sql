WITH "latest_pkg" AS (
    SELECT "Name",
           "Version",
           "UpstreamPublishedAt"
    FROM "package_query_db"."packageinfo"
    WHERE "System" = 'NPM'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY "Name" ORDER BY "UpstreamPublishedAt" DESC) = 1
),
"pkg_proj" AS (
    SELECT lp."Name",
           lp."Version",
           ppv."ProjectName"
    FROM "latest_pkg" lp
    JOIN "project_packageversion" ppv
      ON ppv."Name" = lp."Name"
     AND ppv."Version" = lp."Version"
     -- If a System column exists in project_packageversion, join on it as well
     -- AND ppv."System" = 'NPM'
),
"star_extracted" AS (
    SELECT p."Name",
           p."Version",
           COALESCE(
               NULLIF(REGEXP_EXTRACT(pi."Project_Information", '([0-9]+) stars', 1), ''),
               NULLIF(REGEXP_EXTRACT(pi."Project_Information", 'stars count of ([0-9]+)', 1), '')
           )::INTEGER AS stars
    FROM "pkg_proj" p
    LEFT JOIN "project_info" pi
      ON pi."Project_Information" LIKE '%' || p."ProjectName" || '%'
    WHERE pi."Project_Information" IS NOT NULL
),
"ranked" AS (
    SELECT "Name",
           "Version",
           stars,
           ROW_NUMBER() OVER (ORDER BY stars DESC NULLS LAST) AS rn
    FROM "star_extracted"
    WHERE stars IS NOT NULL
)
SELECT "Name",
       "Version",
       stars
FROM "ranked"
WHERE rn <= 5
ORDER BY stars DESC, "Name";