WITH target_univ AS (
    SELECT
        CAST(regexp_extract("Patents_info", '(?i)publication (?:number|no\.?)[\s]*([A-Z0-9-]+)', 1) AS TEXT) AS pub_number,
        CASE
            WHEN "cpc" LIKE '[%' THEN json_extract("cpc", '$[0]')
            ELSE "cpc"
        END AS primary_cpc
    FROM "publicationinfo"
    WHERE lower("Patents_info") LIKE '%univ california%'
      AND regexp_extract("Patents_info", '(?i)publication (?:number|no\.?)[\s]*([A-Z0-9-]+)', 1) IS NOT NULL
),

citing AS (
    SELECT
        CAST(regexp_extract(p."Patents_info", '(?i)(?:holds|owned by|assigned to|by)\s+([^,\.]+)', 1) AS TEXT) AS citing_assignee,
        json_extract(cit.value, '$.publication_number') AS cited_pub_number
    FROM "publicationinfo" p
    JOIN json_each(p."citation") cit ON p."citation" LIKE '[%]' AND cit.value IS NOT NULL
),

filtered_citing AS (
    SELECT DISTINCT citing_assignee, cited_pub_number
    FROM citing
    WHERE citing_assignee IS NOT NULL
      AND lower(citing_assignee) NOT LIKE '%univ california%'
)
SELECT DISTINCT
    fc.citing_assignee,
    d."titleFull" AS cpc_title
FROM filtered_citing fc
JOIN target_univ tu ON tu.pub_number = fc.cited_pub_number
JOIN "cpc_definition" d ON d."symbol" = tu.primary_cpc
ORDER BY fc.citing_assignee;