SELECT 
    CAST(SUBSTR(Movie.year, -4) AS INTEGER) AS year, 
    COUNT(DISTINCT Movie.MID) AS total_movies, 
    COUNT(DISTINCT CASE WHEN exclusively_female.count = total_cast.count THEN Movie.MID END) * 100.0 / COUNT(DISTINCT Movie.MID) AS percentage_exclusively_female
FROM 
    Movie
LEFT JOIN 
    M_Cast ON Movie.MID = M_Cast.MID
LEFT JOIN 
    Person ON M_Cast.PID = Person.PID
LEFT JOIN (
    SELECT 
        M_Cast.MID, 
        COUNT(*) AS count
    FROM 
        M_Cast
    JOIN 
        Person ON M_Cast.PID = Person.PID
    WHERE 
        Person.Gender = 'Female'
    GROUP BY 
        M_Cast.MID
) AS exclusively_female ON Movie.MID = exclusively_female.MID
LEFT JOIN (
    SELECT 
        M_Cast.MID, 
        COUNT(*) AS count
    FROM 
        M_Cast
    GROUP BY 
        M_Cast.MID
) AS total_cast ON Movie.MID = total_cast.MID
GROUP BY 
    CAST(SUBSTR(Movie.year, -4) AS INTEGER)
ORDER BY 
    year;