WITH users_2016 AS (
    SELECT u.user_id
    FROM "user" u
    WHERE COALESCE(
            NULLIF(regexp_extract(u.yelping_since, '(19[0-9]{2}|20[0-9]{2})', 1), ''),
            NULLIF(regexp_extract(u.yelping_since, '(\\d{4})', 1), '')
          )::INTEGER = 2016
),
reviews_filtered AS (
    SELECT r.review_id,
           r.user_id,
           r.business_ref,
           COALESCE(
               NULLIF(regexp_extract(r.date, '(19[0-9]{2}|20[0-9]{2})', 1), ''),
               NULLIF(regexp_extract(r.date, '(\\d{4})', 1), '')
           )::INTEGER AS review_year
    FROM "review" r
    WHERE COALESCE(
              NULLIF(regexp_extract(r.date, '(19[0-9]{2}|20[0-9]{2})', 1), ''),
              NULLIF(regexp_extract(r.date, '(\\d{4})', 1), '')
          )::INTEGER >= 2016
),
user_reviews AS (
    SELECT DISTINCT r.review_id, r.business_ref
    FROM reviews_filtered r
    JOIN users_2016 u ON r.user_id = u.user_id
),
business_categories AS (
    SELECT b.business_id,
           COALESCE(
               NULLIF(regexp_extract(b.description, 'in the categor(?:y|ies) of ["'']+([A-Za-z, /&()''-]+)["'']+', 1), ''),
               NULLIF(regexp_extract(b.description, ', including ([A-Za-z, /&()''-]+)\\.', 1), ''),
               NULLIF(regexp_extract(b.description, 'services[ ]+(?:in|including) ([A-Za-z, /&()''-]+)\\.', 1), ''),
               NULLIF(regexp_extract(b.description, '(?:options in|(?:range of )?solutions in) ([A-Za-z, /&()''-]+)\\.', 1), ''),
               NULLIF(regexp_extract(b.description, 'categor(?:y|ies) such as ([A-Za-z, /&()''-]+)\\.', 1), ''),
               NULLIF(regexp_extract(b.description, 'selection of ([A-Za-z, /&()''-]+)', 1), '')
           ) AS cat_str
    FROM "businessinfo_database"."business" b
    WHERE b.description IS NOT NULL
),
review_categories AS (
    SELECT TRIM(cat) AS category,
           COUNT(DISTINCT ur.review_id) AS review_cnt
    FROM user_reviews ur
    JOIN business_categories bc
      ON REPLACE(ur.business_ref, 'businessref_', 'businessid_') = bc.business_id
    CROSS JOIN UNNEST(regexp_split_to_array(bc.cat_str, ', | and ')) AS t(cat)
    WHERE bc.cat_str IS NOT NULL AND bc.cat_str <> ''
    GROUP BY TRIM(cat)
)
SELECT category,
       review_cnt
FROM review_categories
ORDER BY review_cnt DESC
LIMIT 5;