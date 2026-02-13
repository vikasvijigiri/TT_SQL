WITH RatedMovies AS (
    SELECT m.id AS movie_id, r.avg_rating
    FROM movies m
    JOIN ratings r ON m.id = r.movie_id
    WHERE r.avg_rating > 8
),
TopGenres AS (
    SELECT g.genre, COUNT(*) AS movie_count
    FROM RatedMovies rm
    JOIN genre g ON rm.movie_id = g.movie_id
    GROUP BY g.genre
    ORDER BY movie_count DESC
    LIMIT 3
),
FilteredMovies AS (
    SELECT rm.movie_id, g.genre
    FROM RatedMovies rm
    JOIN genre g ON rm.movie_id = g.movie_id
    WHERE g.genre IN (SELECT genre FROM TopGenres)
),
DirectorGenreCounts AS (
    SELECT dm.name_id, fm.genre, COUNT(*) AS movie_count
    FROM FilteredMovies fm
    JOIN director_mapping dm ON fm.movie_id = dm.movie_id
    GROUP BY dm.name_id, fm.genre
),
RankedDirectors AS (
    SELECT name_id, SUM(movie_count) AS total_movie_count,
           ROW_NUMBER() OVER (ORDER BY SUM(movie_count) DESC) AS rank
    FROM DirectorGenreCounts
    GROUP BY name_id
)
SELECT n.name, rd.total_movie_count
FROM RankedDirectors rd
JOIN names n ON rd.name_id = n.id
WHERE rd.rank <= 4
ORDER BY rd.total_movie_count DESC;