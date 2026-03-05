SELECT material, prod_desc, doh_incl_git_fg_wip
FROM "acme-chatbot".doh
ORDER BY doh_incl_git_fg_wip DESC
LIMIT 10