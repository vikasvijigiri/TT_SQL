SELECT 
  COUNT(*) AS total,
  SUM(CASE WHEN shelf_life___11 > 0 THEN 1 ELSE 0 END) AS shelf_life_lt_11,
  SUM(CASE WHEN shelf_life_bet_11_and_16 > 0 THEN 1 ELSE 0 END) AS shelf_life_11_to_16,
  SUM(CASE WHEN shelf_life__16 > 0 THEN 1 ELSE 0 END) AS shelf_life_gt_16
FROM "acme-chatbot".doh