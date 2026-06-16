WITH "release_packages" AS (
    SELECT DISTINCT "Name", "Version"
    FROM "package_query_db"."packageinfo"
    WHERE "System" = 'NPM'
      AND json_extract_string("VersionInfo", '$.IsRelease') = 'true'
),
"release_projects" AS (
    SELECT DISTINCT "ProjectName"
    FROM "project_packageversion" pv
    JOIN "release_packages" rp
      ON pv."Name" = rp."Name"
     AND pv."Version" = rp."Version"
     AND pv."System" = 'NPM'
),
"project_info_parsed" AS (
    SELECT
        regexp_extract("Project_Information", 'The project ([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)', 1) AS project_name,
        TRY_CAST(
            REPLACE(
                COALESCE(
                    NULLIF(regexp_extract("Project_Information", '([0-9]+) forks', 1), ''),
                    NULLIF(regexp_extract("Project_Information", 'forks count of ([0-9]+)', 1), ''),
                    NULLIF(regexp_extract("Project_Information", 'forked ([0-9]+) times', 1), '')
                ),
                ',',
                ''
            ) AS BIGINT
        ) AS forks,
        "Licenses"
    FROM "project_info"
    WHERE "Project_Information" LIKE '%fork%'
),
"filtered_projects" AS (
    SELECT pi.project_name, pi.forks
    FROM "project_info_parsed" pi
    JOIN "release_projects" rp
      ON lower(pi.project_name) = lower(rp."ProjectName")
    WHERE pi.forks IS NOT NULL
      AND pi."Licenses" LIKE '%MIT%'
)
SELECT project_name, forks
FROM "filtered_projects"
ORDER BY forks DESC
LIMIT 5;