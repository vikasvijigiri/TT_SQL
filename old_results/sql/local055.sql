WITH ArtistSales AS (
    SELECT ar.ArtistId, ar.Name, SUM(ii.UnitPrice * ii.Quantity) AS TotalSales
    FROM artists ar
    JOIN albums al ON ar.ArtistId = al.ArtistId
    JOIN tracks t ON al.AlbumId = t.AlbumId
    JOIN invoice_items ii ON t.TrackId = ii.TrackId
    GROUP BY ar.ArtistId, ar.Name
),
TopArtist AS (
    SELECT ArtistId, Name, TotalSales
    FROM ArtistSales
    WHERE TotalSales = (SELECT MAX(TotalSales) FROM ArtistSales)
    ORDER BY Name ASC
    LIMIT 1
),
LowestArtist AS (
    SELECT ArtistId, Name, TotalSales
    FROM ArtistSales
    WHERE TotalSales = (SELECT MIN(TotalSales) FROM ArtistSales WHERE TotalSales > 0)
    ORDER BY TotalSales ASC, Name ASC
    LIMIT 1
),
CustomerSpending AS (
    SELECT c.CustomerId, ar.ArtistId, ar.Name AS ArtistName, SUM(ii.UnitPrice * ii.Quantity) AS TotalSpent
    FROM customers c
    JOIN invoices i ON c.CustomerId = i.CustomerId
    JOIN invoice_items ii ON i.InvoiceId = ii.InvoiceId
    JOIN tracks t ON ii.TrackId = t.TrackId
    JOIN albums al ON t.AlbumId = al.AlbumId
    JOIN artists ar ON al.ArtistId = ar.ArtistId
    WHERE ar.ArtistId IN (SELECT ArtistId FROM TopArtist UNION SELECT ArtistId FROM LowestArtist)
    GROUP BY c.CustomerId, ar.ArtistId, ar.Name
),
AverageSpending AS (
    SELECT ArtistName, AVG(TotalSpent) AS AvgSpent
    FROM CustomerSpending
    WHERE TotalSpent > 0
    GROUP BY ArtistName
)
SELECT ABS(
    COALESCE((SELECT AvgSpent FROM AverageSpending WHERE ArtistName = (SELECT Name FROM TopArtist)), 0) -
    COALESCE((SELECT AvgSpent FROM AverageSpending WHERE ArtistName = (SELECT Name FROM LowestArtist)), 0)
) AS AbsoluteDifference;