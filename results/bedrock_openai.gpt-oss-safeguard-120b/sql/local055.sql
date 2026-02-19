WITH track_artist AS (
    SELECT t.TrackId,
           ar.ArtistId,
           ar.Name AS artist_name
    FROM tracks t
    JOIN albums al ON t.AlbumId = al.AlbumId
    JOIN artists ar ON al.ArtistId = ar.ArtistId
),
artist_sales AS (
    SELECT ta.ArtistId,
           ta.artist_name,
           SUM(ii.UnitPrice * ii.Quantity) AS total_sales
    FROM invoice_items ii
    JOIN track_artist ta ON ii.TrackId = ta.TrackId
    GROUP BY ta.ArtistId
),
top_artist AS (
    SELECT ArtistId,
           artist_name
    FROM artist_sales
    ORDER BY total_sales DESC, LOWER(artist_name) ASC
    LIMIT 1
),
low_artist AS (
    SELECT ArtistId,
           artist_name
    FROM artist_sales
    ORDER BY total_sales ASC, LOWER(artist_name) ASC
    LIMIT 1
),
customer_spends AS (
    SELECT i.CustomerId,
           ta.ArtistId,
           SUM(ii.UnitPrice * ii.Quantity) AS spend
    FROM invoice_items ii
    JOIN invoices i ON ii.InvoiceId = i.InvoiceId
    JOIN track_artist ta ON ii.TrackId = ta.TrackId
    WHERE ta.ArtistId IN ((SELECT ArtistId FROM top_artist), (SELECT ArtistId FROM low_artist))
    GROUP BY i.CustomerId, ta.ArtistId
),
pivot_spend AS (
    SELECT cs.CustomerId,
           COALESCE(SUM(CASE WHEN cs.ArtistId = (SELECT ArtistId FROM top_artist) THEN cs.spend END), 0) AS top_spend,
           COALESCE(SUM(CASE WHEN cs.ArtistId = (SELECT ArtistId FROM low_artist) THEN cs.spend END), 0) AS low_spend
    FROM customer_spends cs
    GROUP BY cs.CustomerId
),
averages AS (
    SELECT (SELECT artist_name FROM top_artist) AS top_artist_name,
           (SELECT artist_name FROM low_artist) AS low_artist_name,
           (SELECT AVG(top_spend) FROM pivot_spend WHERE top_spend > 0) AS avg_top_spend,
           (SELECT AVG(low_spend) FROM pivot_spend WHERE low_spend > 0) AS avg_low_spend,
           ABS((SELECT AVG(top_spend) FROM pivot_spend WHERE top_spend > 0) -
               (SELECT AVG(low_spend) FROM pivot_spend WHERE low_spend > 0)) AS diff_spend
)
SELECT a.top_artist_name,
       a.low_artist_name,
       p.CustomerId,
       p.top_spend,
       p.low_spend,
       a.avg_top_spend,
       a.avg_low_spend,
       a.diff_spend
FROM averages a
CROSS JOIN pivot_spend p
ORDER BY p.CustomerId;