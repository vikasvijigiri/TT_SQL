WITH RECURSIVE
    split(word, pos, ch) AS (
        SELECT words, 1, substr(words, 1, 1) FROM word_list
        UNION ALL
        SELECT word, pos + 1, substr(word, pos + 1, 1)
        FROM split
        WHERE pos < length(word)
    ),
    signatures AS (
        SELECT word,
               GROUP_CONCAT(ch, '') AS signature
        FROM (
            SELECT word, ch
            FROM split
            ORDER BY word, ch
        )
        GROUP BY word
    ),
    filtered AS (
        SELECT w.words, s.signature
        FROM word_list w
        JOIN signatures s ON w.words = s.word
        WHERE length(w.words) BETWEEN 4 AND 5
          AND substr(w.words, 1, 1) = 'r'
    ),
    anagram_groups AS (
        SELECT signature, COUNT(*) AS group_size
        FROM filtered
        GROUP BY signature
        HAVING COUNT(*) > 1
    )
SELECT f.words,
       (ag.group_size - 1) AS anagram_count
FROM filtered f
JOIN anagram_groups ag ON f.signature = ag.signature
ORDER BY f.words
LIMIT 10;