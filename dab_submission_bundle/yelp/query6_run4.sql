WITH "parsed_reviews" AS (
    SELECT
        REPLACE(r."business_ref", 'businessref_', '') AS biz_key,
        r."rating",
        COALESCE(
            TRY_STRPTIME(r."date", '%B %d, %Y at %I:%M %p'),
            TRY_STRPTIME(r."date", '%d %b %Y')
        ) AS review_ts
    FROM "review" r
    WHERE COALESCE(
            TRY_STRPTIME(r."date", '%B %d, %Y at %I:%M %p'),
            TRY_STRPTIME(r."date", '%d %b %Y')
          ) BETWEEN DATE '2016-01-01' AND DATE '2016-06-30'
),
"biz_stats" AS (
    SELECT
        b."business_id",
        b."name" AS business_name,
        b."description",
        COUNT(*) AS review_cnt,
        AVG(rating)::DOUBLE AS avg_rating
    FROM "parsed_reviews" pr
    JOIN "business" b
      ON REPLACE(b."business_id", 'businessid_', '') = pr.biz_key
    GROUP BY b."business_id", b."name", b."description"
    HAVING COUNT(*) >= 5
),
"category_extracted" AS (
    SELECT
        bs."business_id",
        bs."business_name",
        bs."avg_rating",
        COALESCE(
            NULLIF(regexp_extract(bs."description", 'in the categor(?:y|ies) of ["\'']+([A-Za-z, /&()''-]+)["\'']+', 1), ''),
            NULLIF(regexp_extract(bs."description", 'services[[:space:]]*(?:in|including) ([^.]+)[.]', 1), ''),
            NULLIF(regexp_extract(bs."description", '(?:mix of|ranging from|services in|array of (?:dishes |options )?in) ([^.]+)[.]', 1), ''),
            bs."description" -- fallback to full description if no pattern matches
        ) AS category
    FROM "biz_stats" bs
)
SELECT
    c."business_name",
    c."avg_rating",
    c."category"
FROM "category_extracted" c
ORDER BY c."avg_rating" DESC
LIMIT 1;