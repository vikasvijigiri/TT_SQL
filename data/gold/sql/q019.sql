SELECT 
  reporting_month,
  ROUND(AVG(doh::bigint), 2) AS avg_doh,
  ROUND(AVG(doh_incl_git_fg::bigint), 2) AS avg_doh_incl_git_fg
FROM "acme-chatbot".doh
GROUP BY reporting_month
ORDER BY reporting_month