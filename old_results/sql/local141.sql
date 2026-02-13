SELECT sp.businessentityid AS salesperson_id, 
       strftime('%Y', soh.orderdate) AS year, 
       SUM(soh.subtotal) AS total_sales, 
       SUM(sph.SalesQuota) AS annual_sales_quota, 
       SUM(soh.subtotal) - SUM(sph.SalesQuota) AS difference 
FROM salesorderheader soh 
JOIN salesperson sp ON soh.salespersonid = sp.businessentityid 
JOIN SalesPersonQuotaHistory sph ON sp.businessentityid = sph.BusinessEntityID 
    AND strftime('%Y', soh.orderdate) = strftime('%Y', sph.QuotaDate) 
GROUP BY sp.businessentityid, strftime('%Y', soh.orderdate) 
ORDER BY sp.businessentityid, year;