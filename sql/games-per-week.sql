SELECT
    DATE_TRUNC('week', DATE(games.created_at)) AS week
    , COUNT(games.id) AS games
FROM games
WHERE games.status = 'started'
GROUP BY week
ORDER BY week
;
