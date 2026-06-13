WITH cc_biz AS (
    SELECT business_id, description FROM business_db.business
    WHERE json_extract_string(attributes, '$.BusinessAcceptsCreditCards') = 'True'
),
cat_str AS (
    SELECT business_id, COALESCE(
        NULLIF(regexp_extract(description, 'in the categor(?:y|ies) of [''"]+([A-Za-z, /&]+)[''"]+', 1), ''),
        NULLIF(regexp_extract(description, 'services[, ]+(?:in|including) ([A-Za-z, /&]+?)[.]', 1), ''),
        NULLIF(regexp_extract(description, '(?:mix of|ranging from|options in|services in|array of (?:dishes |options )?in) ([A-Za-z, /&]+?)[.]', 1), ''),
        NULLIF(regexp_extract(description, 'in the (?:fields?|categor(?:y|ies)) of ([A-Za-z, /&]+?)[.]', 1), '')
    ) AS cats FROM cc_biz
),
cat_list AS (
    SELECT business_id, TRIM(UNNEST(regexp_split_to_array(cats, ', | and '))) AS category
    FROM cat_str WHERE cats IS NOT NULL AND cats != ''
),
top_cat AS (
    SELECT category FROM cat_list
    WHERE TRIM(category) != '' AND LENGTH(TRIM(category)) > 1
    GROUP BY category ORDER BY COUNT(DISTINCT business_id) DESC LIMIT 1
)
SELECT tc.category, COUNT(DISTINCT b.business_id) AS biz_cnt, AVG(r.rating) AS avg_rating
FROM top_cat tc
JOIN business_db.business b
    ON json_extract_string(b.attributes, '$.BusinessAcceptsCreditCards') = 'True'
    AND b.description LIKE '%' || tc.category || '%'
JOIN review r ON REPLACE(r.business_ref, 'businessref_', '') = REPLACE(b.business_id, 'businessid_', '')
GROUP BY tc.category