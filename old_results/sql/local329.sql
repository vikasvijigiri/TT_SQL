SELECT COUNT(DISTINCT a.session) AS unique_sessions
FROM activity_log a
JOIN activity_log b ON a.session = b.session
WHERE a.path = '/regist/input'
  AND b.path = '/regist/confirm'
  AND a.stamp < b.stamp