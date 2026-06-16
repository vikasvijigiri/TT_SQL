WITH
    filtered_patents AS (
        SELECT rowid AS pub_id,
               "Patents_info",
               "grant_date",
               "filing_date",
               "cpc"
        FROM "publicationinfo"
        WHERE lower("Patents_info") LIKE '%germany%'
          AND lower("grant_date") LIKE '%2019%'
          AND (
                lower("grant_date") LIKE '%july%'
                OR lower("grant_date") LIKE '%august%'
                OR lower("grant_date") LIKE '%september%'
                OR lower("grant_date") LIKE '%october%'
                OR lower("grant_date") LIKE '%november%'
                OR lower("grant_date") LIKE '%december%'
              )
          AND "cpc" IS NOT NULL
    ),
    cpc_exploded AS (
        SELECT fp.pub_id,
               upper(trim(json_extract(je.value, '$.code'))) AS cpc_code,
               cd."titleFull" AS cpc_title,
               CAST(regexp_extract(fp."filing_date", '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) AS filing_year
        FROM filtered_patents fp
        CROSS JOIN json_each(fp."cpc") je
        JOIN "cpc_definition" cd
          ON cd."symbol" = upper(trim(json_extract(je.value, '$.code')))
         AND cd."level" = 4
        WHERE filing_year IS NOT NULL
    ),
    yearly_counts AS (
        SELECT cpc_code,
               cpc_title,
               filing_year,
               COUNT(DISTINCT pub_id) AS filings
        FROM cpc_exploded
        GROUP BY cpc_code, cpc_title, filing_year
    ),
    ordered_counts AS (
        SELECT yc.*, 
               ROW_NUMBER() OVER (PARTITION BY cpc_code ORDER BY filing_year) AS seq
        FROM yearly_counts yc
    ),
    ema_recursive AS (
        SELECT oc.cpc_code,
               oc.cpc_title,
               oc.filing_year,
               oc.filings,
               CAST(oc.filings AS REAL) AS ema,
               oc.seq
        FROM ordered_counts oc
        WHERE oc.seq = 1
        UNION ALL
        SELECT oc.cpc_code,
               oc.cpc_title,
               oc.filing_year,
               oc.filings,
               (0.1 * oc.filings) + (0.9 * er.ema) AS ema,
               oc.seq
        FROM ema_recursive er
        JOIN ordered_counts oc
          ON oc.cpc_code = er.cpc_code
         AND oc.seq = er.seq + 1
    ),
    ranked_best AS (
        SELECT er.cpc_code,
               er.cpc_title,
               er.filing_year AS best_year,
               er.ema,
               ROW_NUMBER() OVER (PARTITION BY er.cpc_code ORDER BY er.ema DESC) AS rn
        FROM ema_recursive er
    )
SELECT
    "cpc_code" AS "CPC_Code",
    "cpc_title" AS "CPC_Title",
    "best_year" AS "Best_Year",
    "ema" AS "EMA"
FROM ranked_best
WHERE rn = 1
ORDER BY "EMA" DESC;