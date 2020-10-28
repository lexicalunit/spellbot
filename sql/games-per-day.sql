SELECT
    DATE(games.created_at) AS day
    , COUNT(games.id) AS games
FROM games
WHERE games.status = 'started'
GROUP BY day
ORDER BY day
;
