WITH users_2016 AS (
    SELECT u.user_id
    FROM "user" u
    WHERE COALESCE(
            NULLIF(regexp_extract(u.yelping_since, '(19[0-9]{2}|20[0-9]{2})', 1), ''),
            NULLIF(regexp_extract(u.yelping_since, '(\\d{4})', 1), '')
          )::INTEGER = 2016
),
reviews_2016_plus AS (
    SELECT r.review_id,
           r.user_id,
           r.business_ref,
           COALESCE(
               NULLIF(regexp_extract(r.date, '(19[0-9]{2}|20[0-9]{2})', 1), ''),
               NULLIF(regexp_extract(r.date, '(\\d{4})', 1), '')
           )::INTEGER AS review_year
    FROM "review" r
),
filtered_reviews AS (
    SELECT r.review_id, r.business_ref
    FROM reviews_2016_plus r
    JOIN users_2016 u ON r.user_id = u.user_id
    WHERE r.review_year >= 2016
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
    FROM "business" b
    WHERE b.description IS NOT NULL
),
review_categories AS (
    SELECT TRIM(cat) AS category,
           fr.review_id
    FROM filtered_reviews fr
    JOIN business_categories bc
      ON REPLACE(fr.business_ref, 'businessref_', 'businessid_') = bc.business_id
    CROSS JOIN UNNEST(regexp_split_to_array(bc.cat_str, ', | and ')) AS t(cat)
    WHERE bc.cat_str IS NOT NULL AND bc.cat_str <> ''
)
SELECT rc.category,
       COUNT(DISTINCT rc.review_id) AS total_reviews
FROM review_categories rc
GROUP BY rc.category
ORDER BY total_reviews DESC
LIMIT 5;