SELECT s.StudLastName, 
       CASE 
           WHEN CAST(rnk AS REAL) / total_students <= 0.2 THEN 'First'
           WHEN CAST(rnk AS REAL) / total_students <= 0.4 THEN 'Second'
           WHEN CAST(rnk AS REAL) / total_students <= 0.6 THEN 'Third'
           WHEN CAST(rnk AS REAL) / total_students <= 0.8 THEN 'Fourth'
           ELSE 'Fifth'
       END AS Quintile
FROM (
    SELECT ss.StudentID, 
           ss.Grade, 
           s.StudLastName, 
           (SELECT COUNT(*) FROM Student_Schedules ss2 
            JOIN Classes c2 ON ss2.ClassID = c2.ClassID
            JOIN Subjects sub2 ON c2.SubjectID = sub2.SubjectID
            WHERE ss2.ClassStatus = 2
              AND sub2.SubjectName = 'English'
              AND ss2.Grade >= ss.Grade) AS rnk,
           (SELECT COUNT(*) FROM Student_Schedules ss3 
            JOIN Classes c3 ON ss3.ClassID = c3.ClassID
            JOIN Subjects sub3 ON c3.SubjectID = sub3.SubjectID
            WHERE ss3.ClassStatus = 2
              AND sub3.SubjectName = 'English') AS total_students
    FROM Student_Schedules ss
    JOIN Classes c ON ss.ClassID = c.ClassID
    JOIN Subjects sub ON c.SubjectID = sub.SubjectID
    JOIN Students s ON ss.StudentID = s.StudentID
    WHERE ss.ClassStatus = 2
      AND sub.SubjectName = 'English'
) AS ranked_students
ORDER BY Quintile, StudLastName;