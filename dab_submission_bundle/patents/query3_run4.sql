WITH "cited_univ" AS (
    SELECT
        COALESCE(
            regexp_extract("Patents_info", '^(.*?) holds', 1),
            regexp_extract("Patents_info", 'owned by ([^]+)', 1),
            regexp_extract("Patents_info", 'assigned to ([^]+)', 1)
        ) AS "assignee",
        regexp_extract("Patents_info", 'publication number\s*([A-Z0-9-]+)', 1) AS "pub_number",
        json_extract("cpc", '$[0]') AS "primary_cpc"
    FROM "publicationinfo"
    WHERE COALESCE(
            regexp_extract("Patents_info", '^(.*?) holds', 1),
            regexp_extract("Patents_info", 'owned by ([^]+)', 1),
            regexp_extract("Patents_info", 'assigned to ([^]+)', 1)
        ) LIKE '%UNIV CALIFORNIA%'
        AND "pub_number" IS NOT NULL
),
"citing" AS (
    SELECT
        COALESCE(
            regexp_extract(p."Patents_info", '^(.*?) holds', 1),
            regexp_extract(p."Patents_info", 'owned by ([^]+)', 1),
            regexp_extract(p."Patents_info", 'assigned to ([^]+)', 1)
        ) AS "citing_assignee",
        json_extract(cit.value, '$.publication_number') AS "cited_pub_number"
    FROM "publicationinfo" p
    JOIN json_each(p."citation") cit ON 1=1
    WHERE p."citation" IS NOT NULL
        AND json_extract(cit.value, '$.publication_number') IS NOT NULL
        AND COALESCE(
            regexp_extract(p."Patents_info", '^(.*?) holds', 1),
            regexp_extract(p."Patents_info", 'owned by ([^]+)', 1),
            regexp_extract(p."Patents_info", 'assigned to ([^]+)', 1)
        ) NOT LIKE '%UNIV CALIFORNIA%'
)
SELECT DISTINCT
    c."citing_assignee" AS "citing_assignee",
    d."titleFull" AS "cpc_title"
FROM "citing" c
JOIN "cited_univ" cu ON cu."pub_number" = c."cited_pub_number"
JOIN "cpc_definition" d ON cu."primary_cpc" = d."symbol"
WHERE c."citing_assignee" IS NOT NULL
ORDER BY c."citing_assignee";