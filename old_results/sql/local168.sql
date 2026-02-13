/* Corrected query – uses the proper linking table `skills_job_dim`
   and avoids unsupported ILIKE syntax by using LOWER() with LIKE. */
SELECT
    jp.job_posting_id,
    jp.title,
    jp.description,
    GROUP_CONCAT(s.skill_name, ', ') AS skill_list
FROM
    job_postings AS jp
    /* link job postings to their required skills */
    JOIN skills_job_dim AS sjd
        ON jp.job_posting_id = sjd.job_posting_id
    /* bring in the human‑readable skill name */
    JOIN skills AS s
        ON sjd.skill_id = s.skill_id
WHERE
    /* case‑insensitive search on the posting title */
    LOWER(jp.title) LIKE '%' || LOWER('data') || '%'
    /* optional filter on a specific skill (example) */
    AND LOWER(s.skill_name) LIKE '%' || LOWER('python') || '%'
GROUP BY
    jp.job_posting_id,
    jp.title,
    jp.description;