import duckdb, sys
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_DEPS_DEV_V1\query_dataset'
conn = duckdb.connect(f'{base}/project_query.db', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/package_query.db' AS pkg_db (TYPE sqlite)")

# Check @dollarshaveclub/cli as simple package
print("=== @dollarshaveclub/cli simple package ===")
r1 = conn.execute("""
    SELECT Name, Version, json_extract_string(VersionInfo, '$.IsRelease') as IsRelease,
           json_extract_string(VersionInfo, '$.Ordinal') as Ordinal, UpstreamPublishedAt
    FROM pkg_db.packageinfo
    WHERE System='NPM' AND Name='@dollarshaveclub/cli'
    ORDER BY UpstreamPublishedAt DESC NULLS LAST
    LIMIT 10
""").fetchdf()
print(r1.to_string())

# project_packageversion for @dollarshaveclub/cli simple
print("\n=== project_packageversion for @dollarshaveclub/cli simple ===")
r2 = conn.execute("""
    SELECT Name, Version, ProjectName, ProjectType
    FROM project_packageversion
    WHERE Name='@dollarshaveclub/cli'
    LIMIT 10
""").fetchdf()
print(r2.to_string())

# Star count for @dollarshaveclub/cli
print("\n=== Stars for @dollarshaveclub/cli GitHub project ===")
r3 = conn.execute("""
    SELECT
        REGEXP_EXTRACT(pi.Project_Information, 'The project ([^ ]+)', 1) AS project_name,
        TRY_CAST(REPLACE(COALESCE(
            NULLIF(REGEXP_EXTRACT(pi.Project_Information, '([0-9,]+) stars', 1), ''),
            NULLIF(REGEXP_EXTRACT(pi.Project_Information, 'stars count of ([0-9,]+)', 1), ''),
            NULLIF(REGEXP_EXTRACT(pi.Project_Information, 'total of ([0-9,]+) stars', 1), '')
        ), ',', '') AS INTEGER) as stars
    FROM project_info pi
    WHERE pi.Project_Information ILIKE '%dollarshaveclub%'
    LIMIT 5
""").fetchdf()
print(r3.to_string())

# What IS the correct top-5 with proper dedup?
# Try: deduplicate by ProjectName (keep one per GitHub project)
print("\n=== Top 5 with dedup by ProjectName ===")
r4 = conn.execute("""
    WITH latest_npm AS (
        SELECT pi.Name, pi.Version,
               ROW_NUMBER() OVER (PARTITION BY pi.Name ORDER BY
                   COALESCE(CAST(json_extract_string(pi.VersionInfo, '$.Ordinal') AS INTEGER), 0) DESC,
                   pi.UpstreamPublishedAt DESC NULLS LAST
               ) AS rn
        FROM pkg_db.packageinfo pi
        WHERE pi.System = 'NPM'
          AND json_extract_string(pi.VersionInfo, '$.IsRelease') = 'true'
    ),
    latest_only AS (SELECT Name, Version FROM latest_npm WHERE rn=1),
    with_project AS (
        SELECT lo.Name, lo.Version, pv.ProjectName
        FROM latest_only lo
        JOIN project_packageversion pv ON pv.Name=lo.Name AND pv.Version=lo.Version AND pv.System='NPM'
        WHERE pv.ProjectType='GITHUB'
    ),
    with_stars AS (
        SELECT wp.Name, wp.Version, wp.ProjectName,
               TRY_CAST(REPLACE(COALESCE(
                   NULLIF(REGEXP_EXTRACT(pi.Project_Information, '([0-9,]+) stars', 1), ''),
                   NULLIF(REGEXP_EXTRACT(pi.Project_Information, 'stars count of ([0-9,]+)', 1), ''),
                   NULLIF(REGEXP_EXTRACT(pi.Project_Information, 'total of ([0-9,]+) stars', 1), '')
               ), ',', '') AS INTEGER) AS stars
        FROM with_project wp
        JOIN project_info pi ON REGEXP_EXTRACT(pi.Project_Information, 'The project ([^ ]+)', 1) = wp.ProjectName
        WHERE TRY_CAST(REPLACE(COALESCE(
                   NULLIF(REGEXP_EXTRACT(pi.Project_Information, '([0-9,]+) stars', 1), ''),
                   NULLIF(REGEXP_EXTRACT(pi.Project_Information, 'stars count of ([0-9,]+)', 1), ''),
                   NULLIF(REGEXP_EXTRACT(pi.Project_Information, 'total of ([0-9,]+) stars', 1), '')
               ), ',', '') AS INTEGER) IS NOT NULL
    ),
    deduped AS (
        SELECT Name, Version, ProjectName, MAX(stars) as stars,
               ROW_NUMBER() OVER (PARTITION BY ProjectName ORDER BY MAX(stars) DESC, Name ASC) AS proj_rn
        FROM with_stars
        GROUP BY Name, Version, ProjectName
    )
    SELECT Name, Version, stars
    FROM deduped
    WHERE proj_rn = 1
    ORDER BY stars DESC, Name
    LIMIT 10
""").fetchdf()
print(r4.to_string())

conn.close()
