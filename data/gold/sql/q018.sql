SELECT material, prod_desc, doh, doh_incl_git, coverage_shortage
FROM "acme-chatbot".doh
WHERE coverage_shortage > 0
ORDER BY coverage_shortage DESC