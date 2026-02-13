WITH YashChopraMovies AS (
    SELECT MD.MID
    FROM M_Director MD
    JOIN Person P ON MD.PID = P.PID
    WHERE P.Name = 'Yash Chopra'
),
ActorYashChopraCount AS (
    SELECT MC.PID, COUNT(MC.MID) AS YashChopraFilms
    FROM M_Cast MC
    WHERE MC.MID IN (SELECT MID FROM YashChopraMovies)
    GROUP BY MC.PID
),
ActorDirectorCount AS (
    SELECT MC.PID, MD.PID AS DirectorPID, COUNT(DISTINCT MC.MID) AS DirectorFilms
    FROM M_Cast MC
    JOIN M_Director MD ON MC.MID = MD.MID
    GROUP BY MC.PID, MD.PID
),
ActorMaxDirectorFilms AS (
    SELECT ADC.PID, MAX(ADC.DirectorFilms) AS MaxFilms, ADC.DirectorPID
    FROM ActorDirectorCount ADC
    WHERE ADC.DirectorPID != (SELECT PID FROM Person WHERE Name = 'Yash Chopra')
    GROUP BY ADC.PID
)
SELECT COUNT(*) AS ActorsWithMoreFilmsWithYashChopra
FROM ActorYashChopraCount AYC
LEFT JOIN ActorMaxDirectorFilms AMDF ON AYC.PID = AMDF.PID
WHERE AYC.YashChopraFilms > COALESCE(AMDF.MaxFilms, 0);