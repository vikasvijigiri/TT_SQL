WITH users_2016 AS (
    SELECT u.user_id
    FROM "user" AS u
    WHERE CAST(regexp_extract(u.yelping_since, '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) = 2016
),
reviews_2016 AS (
    SELECT r.review_id, r.user_id, r.business_ref
    FROM "review" AS r
    WHERE CAST(regexp_extract(r.date, '(19[0-9]{2}|20[0-9]{2})', 1) AS INTEGER) >= 2016
),
user_reviews AS (
    SELECT r.review_id, r.business_ref
    FROM reviews_2016 AS r
    JOIN users_2016 AS u ON r.user_id = u.user_id
),
business_cats AS (
    SELECT b.business_id,
           COALESCE(
               NULLIF(regexp_extract(b.description, 'in the categor(?:y|ies) of ["\'']+([A-Za-z, /&()''-]+)["\'']+', 1), ''),
               NULLIF(regexp_extract(b.description, ', including ([A-Za-z, /&()''-]+)\\.', 1), ''),
               NULLIF(regexp_extract(b.description, 'services[ ]+(?:in|including) ([A-Za-z, /&()''-]+)\\.', 1), ''),
               NULLIF(regexp_extract(b.description, '(?:options in|(?:range of )?solutions in) ([A-Za-z, /&()''-]+)\\.', 1), ''),
               NULLIF(regexp_extract(b.description, 'categor(?:y|ies) such as ([A-Za-z, /&()''-]+)\\.', 1), ''),
               NULLIF(regexp_extract(b.description, 'selection of ([A-Za-z, /&()''-]+)', 1), '')
           ) AS cats_raw
    FROM "businessinfo_database"."business" AS b
    WHERE b.description IS NOT NULL
),
review_cats AS (
    SELECT ur.review_id,
           TRIM(cat) AS category
    FROM user_reviews AS ur
    JOIN business_cats AS bc
      ON REPLACE(ur.business_ref, 'businessref_', 'businessid_') = bc.business_id
    CROSS JOIN UNNEST(regexp_split_to_array(bc.cats_raw, ', | and ')) AS t(cat)
    WHERE bc.cats_raw IS NOT NULL AND bc.cats_raw <> ''
)
SELECT rc.category,
       COUNT(DISTINCT rc.review_id) AS total_reviews
FROM review_cats AS rc
GROUP BY rc.category
ORDER BY total_reviews DESC
LIMIT 5;