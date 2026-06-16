WITH "release_packages" AS (
    SELECT DISTINCT "Name", "Version"
    FROM "package_query_db"."packageinfo"
    WHERE "System" = 'NPM'
      AND json_extract_string("VersionInfo", '$.IsRelease') = 'true'
),
"release_projects" AS (
    SELECT DISTINCT "ProjectName"
    FROM "project_packageversion" ppv
    JOIN "release_packages" rp
      ON ppv."Name" = rp."Name"
     AND ppv."Version" = rp."Version"
),
"project_info_parsed" AS (
    SELECT
        regexp_extract("Project_Information", '([A-Za-z0-9_-]+/[A-Za-z0-9_-]+)', 1) AS "project_name",
        COALESCE(
            TRY_CAST(
                REPLACE(
                    regexp_extract("Project_Information", '([0-9]+) forks', 1),
                    ',',
                    ''
                ) AS BIGINT
            ),
            0
        ) AS "forks",
        "Licenses"
    FROM "project_info"
    WHERE "Licenses" LIKE '%MIT%'
      AND "Project_Information" IS NOT NULL
),
"filtered_projects" AS (
    SELECT pi."project_name", pi."forks"
    FROM "project_info_parsed" pi
    JOIN "release_projects" rp
      ON LOWER(pi."project_name") = LOWER(rp."ProjectName")
    WHERE pi."project_name" IS NOT NULL
)
SELECT "project_name", "forks"
FROM "filtered_projects"
ORDER BY "forks" DESC
LIMIT 5;