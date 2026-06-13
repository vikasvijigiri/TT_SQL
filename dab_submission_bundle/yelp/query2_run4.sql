WITH "business_state" AS (
    SELECT
        b.business_id,
        REPLACE(b.business_id, 'businessid_', '') AS bid_no,
        COALESCE(
            NULLIF(regexp_extract(b.description, ', ([A-Z]{2})[\s,\.]', 1), ''),
            NULLIF(regexp_extract(b.description, '\\b([A-Z]{2})\\b', 1), '')
        ) AS state
    FROM "business_db"."business" b
    WHERE COALESCE(
            NULLIF(regexp_extract(b.description, ', ([A-Z]{2})[\s,\.]', 1), ''),
            NULLIF(regexp_extract(b.description, '\\b([A-Z]{2})\\b', 1), '')
        ) != ''
)
SELECT
    bs.state,
    COUNT(*) AS review_count,
    AVG(r.rating::DOUBLE) AS avg_rating
FROM "business_state" bs
JOIN "review" r
    ON bs.bid_no = REPLACE(r.business_ref, 'businessref_', '')
GROUP BY bs.state
ORDER BY review_count DESC
LIMIT 1;