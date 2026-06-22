import duckdb, sys
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_DEPS_DEV_V1\query_dataset'

conn = duckdb.connect(f'{base}/project_query.db', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/package_query.db' AS pkg_db (TYPE sqlite)")

# Check VersionInfo.Ordinal for dmrvos typescript entries
print("=== VersionInfo Ordinal for typescript via dmrvos ===")
r1 = conn.execute("""
    SELECT Name, Version, VersionInfo,
           json_extract_string(VersionInfo, '$.IsRelease') as IsRelease,
           json_extract_string(VersionInfo, '$.Ordinal') as Ordinal,
           UpstreamPublishedAt
    FROM pkg_db.packageinfo
    WHERE System='NPM' AND Name LIKE '%dmrvos%typescript%'
    LIMIT 10
""").fetchdf()
print(r1.to_string())

# Check for simple package names (no > in name)
print("\n=== NPM packages WITHOUT > in name (simple packages) sample ===")
r2 = conn.execute("""
    SELECT Name, Version, json_extract_string(VersionInfo, '$.IsRelease') as IsRelease,
           UpstreamPublishedAt
    FROM pkg_db.packageinfo
    WHERE System='NPM' AND INSTR(Name, '>') = 0
    LIMIT 10
""").fetchdf()
print(r2.to_string())

print("\n=== Count simple vs composite packages ===")
r3 = conn.execute("""
    SELECT
        COUNT(CASE WHEN INSTR(Name, '>') = 0 THEN 1 END) as simple_count,
        COUNT(CASE WHEN INSTR(Name, '>') > 0 THEN 1 END) as composite_count,
        COUNT(*) as total
    FROM pkg_db.packageinfo
    WHERE System='NPM'
""").fetchone()
print(f"Simple: {r3[0]}, Composite: {r3[1]}, Total: {r3[2]}")

# Try the correct deduplication: for each DISTINCT composite Name, get latest version
# "distinct NPM package" = distinct Name (including composite key)
# "latest release version" = highest Ordinal or latest UpstreamPublishedAt
print("\n=== Top 5 by stars, deduped by Name (latest by Ordinal) ===")
r4 = conn.execute("""
    WITH latest_npm AS (
        SELECT Name, Version,
               ROW_NUMBER() OVER (PARTITION BY Name ORDER BY
                   COALESCE(CAST(json_extract_string(VersionInfo, '$.Ordinal') AS INTEGER), 0) DESC,
                   UpstreamPublishedAt DESC NULLS LAST
               ) AS rn
        FROM pkg_db.packageinfo
        WHERE System = 'NPM'
          AND json_extract_string(VersionInfo, '$.IsRelease') = 'true'
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
        JOIN project_info pi ON REGEXP_EXTRACT(pi.Project_Information, 'The project ([^ ]+)', 1) = wp.ProjectName
    )
    SELECT Name, Version, MAX(stars) as stars
    FROM with_stars
    WHERE stars IS NOT NULL
    GROUP BY Name, Version
    ORDER BY stars DESC, Name
    LIMIT 10
""").fetchdf()
print(r4.to_string())

conn.close()
