WITH "parsed_reviews" AS (
    SELECT
        REPLACE(r.business_ref, 'businessref_', '') AS biz_key,
        r.rating,
        COALESCE(
            TRY_STRPTIME(r.date, '%B %d, %Y at %I:%M %p'),
            TRY_STRPTIME(r.date, '%d %b %Y')
        ) AS review_ts
    FROM "review" r
    WHERE COALESCE(
            TRY_STRPTIME(r.date, '%B %d, %Y at %I:%M %p'),
            TRY_STRPTIME(r.date, '%d %b %Y')
        ) IS NOT NULL
      AND COALESCE(
            TRY_STRPTIME(r.date, '%B %d, %Y at %I:%M %p'),
            TRY_STRPTIME(r.date, '%d %b %Y')
        ) BETWEEN DATE '2016-01-01' AND DATE '2016-06-30'
),
"biz_stats" AS (
    SELECT
        biz_key,
        COUNT(*) AS review_cnt,
        AVG(rating)::DOUBLE AS avg_rating
    FROM "parsed_reviews"
    GROUP BY biz_key
    HAVING COUNT(*) >= 5
),
"category_extracted" AS (
    SELECT
        b.business_id,
        b.name AS business_name,
        b.description,
        COALESCE(
            NULLIF(regexp_extract(b.description, 'in the categor(?:y|ies) of ["'']+([A-Za-z, /&()''-]+)["'']+', 1), ''),
            NULLIF(regexp_extract(b.description, 'services[[:space:]]*(?:in|including) ([^.]+)[.]', 1), ''),
            NULLIF(regexp_extract(b.description, '(?:mix of|ranging from|services in|array of (?:dishes |options )?in) ([^.]+)[.]', 1), '')
        ) AS category
    FROM "business" b
)
SELECT
    c.business_name,
    bs.avg_rating,
    c.category
FROM "biz_stats" bs
JOIN "category_extracted" c
    ON REPLACE(c.business_id, 'businessid_', '') = bs.biz_key
ORDER BY bs.avg_rating DESC
LIMIT 1;