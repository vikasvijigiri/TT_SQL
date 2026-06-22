import duckdb, sys, sqlite3
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_DEPS_DEV_V1\query_dataset'

# Connect to project DuckDB
conn = duckdb.connect(f'{base}/project_query.db', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/package_query.db' AS pkg_db (TYPE sqlite)")

print("=== packageinfo sample for @dmrvos/infrajs ===")
r = conn.execute("""
    SELECT Name, Version, System, json_extract_string(VersionInfo, '$.IsRelease') as IsRelease, UpstreamPublishedAt
    FROM pkg_db.packageinfo
    WHERE System='NPM' AND Name LIKE '%dmrvos%'
    ORDER BY UpstreamPublishedAt DESC
    LIMIT 10
""").fetchdf()
print(r.to_string())

print("\n=== project_packageversion for @dmrvos/infrajs ===")
r2 = conn.execute("""
    SELECT Name, Version, ProjectName, ProjectType
    FROM project_packageversion
    WHERE Name LIKE '%dmrvos%'
    LIMIT 10
""").fetchdf()
print(r2.to_string())

print("\n=== Top 5 by star count (packageinfo latest release + star extraction) ===")
r3 = conn.execute("""
    WITH latest_npm AS (
        SELECT pi.Name, pi.Version,
               ROW_NUMBER() OVER (PARTITION BY pi.Name ORDER BY pi.UpstreamPublishedAt DESC NULLS LAST) AS rn
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
        SELECT wp.Name, wp.Version,
               TRY_CAST(REPLACE(COALESCE(
                   NULLIF(REGEXP_EXTRACT(pi.Project_Information, '([0-9,]+) stars', 1), ''),
                   NULLIF(REGEXP_EXTRACT(pi.Project_Information, 'stars count of ([0-9,]+)', 1), ''),
                   NULLIF(REGEXP_EXTRACT(pi.Project_Information, 'total of ([0-9,]+) stars', 1), '')
               ), ',', '') AS INTEGER) AS stars
        FROM with_project wp
        JOIN project_info pi ON pi.Project_Information ILIKE '%' || wp.ProjectName || '%'
    )
    SELECT Name, Version, MAX(stars) as stars
    FROM with_stars
    WHERE stars IS NOT NULL
    GROUP BY Name, Version
    ORDER BY stars DESC
    LIMIT 10
""").fetchdf()
print(r3.to_string())

print("\n=== EXPECTED: @dmrvos/infrajs latest version detail ===")
r4 = conn.execute("""
    SELECT pi.Name, pi.Version, json_extract_string(pi.VersionInfo, '$.IsRelease') as IsRelease,
           pi.UpstreamPublishedAt
    FROM pkg_db.packageinfo pi
    WHERE pi.System='NPM' AND pi.Name='@dmrvos/infrajs'
    ORDER BY pi.UpstreamPublishedAt DESC
    LIMIT 5
""").fetchdf()
print(r4.to_string())

conn.close()
