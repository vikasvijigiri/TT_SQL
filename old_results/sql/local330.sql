WITH session_bounds AS (
    SELECT session,
           MIN(stamp) AS min_stamp,
           MAX(stamp) AS max_stamp
    FROM activity_log
    GROUP BY session
),
landing AS (
    SELECT al.session, al.path
    FROM activity_log al
    JOIN session_bounds sb ON al.session = sb.session AND al.stamp = sb.min_stamp
),
exit AS (
    SELECT al.session, al.path
    FROM activity_log al
    JOIN session_bounds sb ON al.session = sb.session AND al.stamp = sb.max_stamp
),
combined AS (
    SELECT session, path FROM landing
    UNION
    SELECT session, path FROM exit
)
SELECT path AS page,
       COUNT(DISTINCT session) AS unique_sessions
FROM combined
GROUP BY path
ORDER BY path;