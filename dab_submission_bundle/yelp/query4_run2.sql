WITH cc_businesses AS (
    SELECT "business_id",
           "description"
    FROM "business_db"."business"
    WHERE json_extract_string("attributes", '$.BusinessAcceptsCreditCards') = 'True'
),
category_extracted AS (
    SELECT "business_id",
           COALESCE(
               NULLIF(regexp_extract("description", 'in the categor(?:y|ies) of ([A-Za-z, /&()''-]+)', 1), ''),
               NULLIF(regexp_extract("description", 'services? (?:in|including) ([A-Za-z, /&()''-]+)', 1), ''),
               NULLIF(regexp_extract("description", '(?:mix of|ranging from|options in|services in|array of (?:dishes |options )?in) ([A-Za-z, /&()''-]+)', 1), ''),
               NULLIF(regexp_extract("description", 'in the (?:fields?|categor(?:y|ies)) of ([A-Za-z, /&()''-]+)', 1), '')
           ) AS cats
    FROM cc_businesses
    WHERE "description" IS NOT NULL
),
category_list AS (
    SELECT "business_id",
           TRIM(UNNEST(regexp_split_to_array(cats, ', | and '))) AS category
    FROM category_extracted
    WHERE cats IS NOT NULL AND cats != ''
),
review_ratings AS (
    SELECT REPLACE(r."business_ref", 'businessref_', 'businessid_') AS "business_id",
           CAST(r."rating" AS DOUBLE) AS rating
    FROM "review" r
    JOIN "business_db"."business" b
      ON REPLACE(r."business_ref", 'businessref_', 'businessid_') = b."business_id"
    WHERE json_extract_string(b."attributes", '$.BusinessAcceptsCreditCards') = 'True'
),
category_stats AS (
    SELECT cl.category,
           COUNT(DISTINCT cl.business_id) AS biz_cnt,
           AVG(rr.rating) AS avg_rating
    FROM category_list cl
    JOIN review_ratings rr ON rr.business_id = cl.business_id
    GROUP BY cl.category
)
SELECT category, biz_cnt, avg_rating
FROM category_stats
ORDER BY biz_cnt DESC
LIMIT 1;