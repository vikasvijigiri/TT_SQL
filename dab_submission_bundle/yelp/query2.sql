WITH "review_tip" AS (
  SELECT r."rating", r."business_ref"
  FROM "review" r
  JOIN "tip" t ON r."text" = t."text"
),
"business_states" AS (
  SELECT b."business_id",
         REGEXP_EXTRACT(b."description", '(Alabama|AL|Alaska|AK|Arizona|AZ|Arkansas|AR|California|CA|Colorado|CO|Connecticut|CT|Delaware|DE|Florida|FL|Georgia|GA|Hawaii|HI|Idaho|ID|Illinois|IL|Indiana|IN|Iowa|IA|Kansas|KS|Kentucky|KY|Louisiana|LA|Maine|ME|Maryland|MD|Massachusetts|MA|Michigan|MI|Minnesota|MN|Mississippi|MS|Missouri|MO|Montana|MT|Nebraska|NE|Nevada|NV|New Hampshire|NH|New Jersey|NJ|New Mexico|NM|New York|NY|North Carolina|NC|North Dakota|ND|Ohio|OH|Oklahoma|OK|Oregon|OR|Pennsylvania|PA|Rhode Island|RI|South Carolina|SC|South Dakota|SD|Tennessee|TN|Texas|TX|Utah|UT|Vermont|VT|Virginia|VA|Washington|WA|West Virginia|WV|Wisconsin|WI|Wyoming|WY)', 1) AS state
  FROM "business_db"."business" b
  WHERE REGEXP_EXTRACT(b."description", '(Alabama|AL|Alaska|AK|Arizona|AZ|Arkansas|AR|California|CA|Colorado|CO|Connecticut|CT|Delaware|DE|Florida|FL|Georgia|GA|Hawaii|HI|Idaho|ID|Illinois|IL|Indiana|IN|Iowa|IA|Kansas|KS|Kentucky|KY|Louisiana|LA|Maine|ME|Maryland|MD|Massachusetts|MA|Michigan|MI|Minnesota|MN|Mississippi|MS|Missouri|MO|Montana|MT|Nebraska|NE|Nevada|NV|New Hampshire|NH|New Jersey|NJ|New Mexico|NM|New York|NY|North Carolina|NC|North Dakota|ND|Ohio|OH|Oklahoma|OK|Oregon|OR|Pennsylvania|PA|Rhode Island|RI|South Carolina|SC|South Dakota|SD|Tennessee|TN|Texas|TX|Utah|UT|Vermont|VT|Virginia|VA|Washington|WA|West Virginia|WV|Wisconsin|WI|Wyoming|WY)', 1) != ''
),
"joined" AS (
  SELECT rt."rating"::DOUBLE AS rating,
         bs.state
  FROM "review_tip" rt
  JOIN "business_states" bs
    ON REPLACE(bs."business_id", 'businessid_', '') = REPLACE(rt."business_ref", 'businessref_', '')
  WHERE bs.state IS NOT NULL AND bs.state != ''
)
SELECT state,
       COUNT(*) AS review_count,
       AVG(rating) AS avg_rating
FROM "joined"
GROUP BY state
ORDER BY review_count DESC
LIMIT 1;