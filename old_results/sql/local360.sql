WITH target_earliest AS (
    SELECT session, MIN(stamp) AS first_target_stamp
    FROM activity_log
    WHERE path IN ('/detail', '/complete')
    GROUP BY session
),
pre_events AS (
    SELECT al.session, al.path, al.search_type, al.stamp
    FROM activity_log al
    JOIN target_earliest te ON al.session = te.session
    WHERE al.search_type <> ''
      AND al.stamp < te.first_target_stamp
),
counts AS (
    SELECT session, COUNT(*) AS cnt
    FROM pre_events
    GROUP BY session
),
min_cnt AS (
    SELECT MIN(cnt) AS min_cnt FROM counts
),
min_sessions AS (
    SELECT c.session
    FROM counts c, min_cnt m
    WHERE c.cnt = m.min_cnt
)
SELECT pe.session, pe.path, pe.search_type
FROM pre_events pe
JOIN min_sessions ms ON pe.session = ms.session
ORDER BY pe.session, pe.stamp;