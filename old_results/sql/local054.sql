WITH ArtistSales AS (
    SELECT ar.ArtistId, ar.Name, SUM(ii.UnitPrice * ii.Quantity) AS TotalSales
    FROM artists ar
    JOIN albums al ON ar.ArtistId = al.ArtistId
    JOIN tracks t ON al.AlbumId = t.AlbumId
    JOIN invoice_items ii ON t.TrackId = ii.TrackId
    GROUP BY ar.ArtistId
),
RankedArtists AS (
    SELECT ArtistId, Name, TotalSales,
           RANK() OVER (ORDER BY TotalSales DESC, ArtistId ASC) AS SalesRank
    FROM ArtistSales
),
BestSellingArtist AS (
    SELECT ArtistId, Name
    FROM RankedArtists
    WHERE SalesRank = 1
),
CustomerSpending AS (
    SELECT c.FirstName, SUM(ii.UnitPrice * ii.Quantity) AS TotalSpent
    FROM customers c
    JOIN invoices i ON c.CustomerId = i.CustomerId
    JOIN invoice_items ii ON i.InvoiceId = ii.InvoiceId
    JOIN tracks t ON ii.TrackId = t.TrackId
    JOIN albums al ON t.AlbumId = al.AlbumId
    JOIN BestSellingArtist bsa ON al.ArtistId = bsa.ArtistId
    GROUP BY c.CustomerId
)
SELECT cs.FirstName, cs.TotalSpent
FROM CustomerSpending cs
WHERE cs.TotalSpent < 1.0;