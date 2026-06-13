WITH users_2016 AS (
    SELECT u.user_id
    FROM "user" u
    WHERE CAST(NULLIF(regexp_extract(u.yelping_since, '(19[0-9]{2}|20[0-9]{2})', 1), '') AS INTEGER) = 2016
),
reviews_2016 AS (
    SELECT r.review_id, r.user_id, r.business_ref
    FROM "review" r
    WHERE CAST(NULLIF(regexp_extract(r.date, '(19[0-9]{2}|20[0-9]{2})', 1), '') AS INTEGER) >= 2016
),
user_reviews AS (
    SELECT r.review_id, r.business_ref
    FROM reviews_2016 r
    JOIN users_2016 u ON r.user_id = u.user_id
),
business_cats AS (
    SELECT b.business_id,
           TRIM(cat) AS category
    FROM "businessinfo_database"."business" b,
         UNNEST(regexp_split_to_array(b.description, ', | and ')) AS t(cat)
    WHERE b.description IS NOT NULL
),
review_cats AS (
    SELECT DISTINCT ur.review_id, bc.category
    FROM user_reviews ur
    JOIN business_cats bc ON REPLACE(ur.business_ref, 'businessref_', 'businessid_') = bc.business_id
)
SELECT rc.category,
       COUNT(DISTINCT rc.review_id) AS total_reviews
FROM review_cats rc
GROUP BY rc.category
ORDER BY total_reviews DESC
LIMIT 5;