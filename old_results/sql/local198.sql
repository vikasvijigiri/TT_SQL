WITH CustomerCounts AS (
    SELECT Country, COUNT(CustomerId) AS CustomerCount
    FROM customers
    GROUP BY Country
    HAVING COUNT(CustomerId) > 4
),
CountrySales AS (
    SELECT i.BillingCountry AS Country, SUM(i.Total) AS TotalSales
    FROM invoices i
    JOIN CustomerCounts cc ON i.BillingCountry = cc.Country
    GROUP BY i.BillingCountry
),
SalesWithRowNumbers AS (
    SELECT TotalSales, ROW_NUMBER() OVER (ORDER BY TotalSales) AS RowAsc, COUNT(*) OVER () AS TotalRows
    FROM CountrySales
)
SELECT AVG(TotalSales) AS MedianSales
FROM SalesWithRowNumbers
WHERE RowAsc = CAST((TotalRows + 1) AS REAL) / 2 OR RowAsc = CAST((TotalRows + 2) AS REAL) / 2;