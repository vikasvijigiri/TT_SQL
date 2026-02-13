WITH ShahrukhMovies AS (
    SELECT DISTINCT M.MID
    FROM M_Cast M
    JOIN Person P ON M.PID = P.PID
    WHERE P.Name = 'Shahrukh Khan'
),
DirectCoActors AS (
    SELECT DISTINCT M.PID
    FROM M_Cast M
    WHERE M.MID IN (SELECT MID FROM ShahrukhMovies)
    AND M.PID != (SELECT PID FROM Person WHERE Name = 'Shahrukh Khan')
),
CoActorMovies AS (
    SELECT DISTINCT M.MID
    FROM M_Cast M
    WHERE M.PID IN (SELECT PID FROM DirectCoActors)
),
IndirectCoActors AS (
    SELECT DISTINCT M.PID
    FROM M_Cast M
    WHERE M.MID IN (SELECT MID FROM CoActorMovies)
    AND M.PID NOT IN (SELECT PID FROM DirectCoActors)
    AND M.MID NOT IN (SELECT MID FROM ShahrukhMovies)
    AND M.PID != (SELECT PID FROM Person WHERE Name = 'Shahrukh Khan')
)
SELECT COUNT(DISTINCT P.PID) AS ShahrukhNumber2Count
FROM IndirectCoActors ICA
JOIN Person P ON ICA.PID = P.PID;