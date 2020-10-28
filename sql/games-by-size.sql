SELECT
    ROUND(games.size) AS size
    , COUNT(1) AS games
    , ROUND(COUNT(1) * 1.0 / (
        SELECT COUNT(1)
        FROM games
        WHERE size IS NOT NULL
    ) * 100.0) AS percent
FROM games
WHERE size IS NOT NULL
GROUP BY size
ORDER BY size
;
