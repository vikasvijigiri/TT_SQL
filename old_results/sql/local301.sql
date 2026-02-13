SELECT
  calendar_year AS year,
  SUM(CASE WHEN week_date BETWEEN date(calendar_year || '-05-18') AND date(calendar_year || '-06-14') THEN sales ELSE 0 END) AS pre_sales,
  SUM(CASE WHEN week_date BETWEEN date(calendar_year || '-06-15') AND date(calendar_year || '-07-12') THEN sales ELSE 0 END) AS post_sales,
  (SUM(CASE WHEN week_date BETWEEN date(calendar_year || '-06-15') AND date(calendar_year || '-07-12') THEN sales ELSE 0 END) -
   SUM(CASE WHEN week_date BETWEEN date(calendar_year || '-05-18') AND date(calendar_year || '-06-14') THEN sales ELSE 0 END))
   / NULLIF(SUM(CASE WHEN week_date BETWEEN date(calendar_year || '-05-18') AND date(calendar_year || '-06-14') THEN sales ELSE 0 END), 0) * 100.0 AS pct_change
FROM cleaned_weekly_sales
WHERE calendar_year IN (2018, 2019, 2020)
GROUP BY calendar_year;