WITH best_artist AS (
    SELECT a.ArtistId
    FROM invoice_items ii
    JOIN tracks t ON ii.TrackId = t.TrackId
    JOIN albums al ON t.AlbumId = al.AlbumId
    JOIN artists a ON al.ArtistId = a.ArtistId
    GROUP BY a.ArtistId
    ORDER BY SUM(ii.UnitPrice * ii.Quantity) DESC
    LIMIT 1
),
customer_spend AS (
    SELECT c.FirstName,
           ROUND(SUM(ii.UnitPrice * ii.Quantity), 2) AS total_spent
    FROM invoice_items ii
    JOIN tracks t ON ii.TrackId = t.TrackId
    JOIN albums al ON t.AlbumId = al.AlbumId
    JOIN best_artist ba ON al.ArtistId = ba.ArtistId
    JOIN invoices inv ON ii.InvoiceId = inv.InvoiceId
    JOIN customers c ON inv.CustomerId = c.CustomerId
    GROUP BY c.CustomerId, c.FirstName
    HAVING total_spent < 1
)
SELECT FirstName, total_spent
FROM customer_spend
ORDER BY FirstName;