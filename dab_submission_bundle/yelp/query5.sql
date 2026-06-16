WITH "wifi_businesses" AS (
    SELECT 
        b."business_id",
        json_extract_string(b."attributes", '$.WiFi') AS wifi,
        regexp_extract(b."description", ', ([A-Z]{2})[\,\s\.]', 1) AS state
    FROM "business" b
    WHERE json_extract_string(b."attributes", '$.WiFi') IS NOT NULL
      AND json_extract_string(b."attributes", '$.WiFi') != ''
      AND LOWER(json_extract_string(b."attributes", '$.WiFi')) NOT LIKE '%no%'
      AND regexp_extract(b."description", ', ([A-Z]{2})[\,\s\.]', 1) != ''
),
"state_counts" AS (
    SELECT 
        state,
        COUNT(DISTINCT "business_id") AS business_cnt
    FROM "wifi_businesses"
    GROUP BY state
),
"top_state" AS (
    SELECT state, business_cnt
    FROM "state_counts"
    ORDER BY business_cnt DESC
    LIMIT 1
)
SELECT 
    ts.state,
    ts.business_cnt AS "business_count",
    AVG(r."rating")::DOUBLE AS "average_rating"
FROM "top_state" ts
JOIN "wifi_businesses" wb ON wb.state = ts.state
JOIN "review" r ON r."business_ref" = wb."business_id"
GROUP BY ts.state, ts.business_cnt;
