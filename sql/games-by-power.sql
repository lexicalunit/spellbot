SELECT
    ROUND(games.game_power) AS power
    , COUNT(1) AS games
    , ROUND(COUNT(1) * 1.0 / (
        SELECT COUNT(1)
        FROM games
        WHERE game_power IS NOT NULL
    ) * 100.0) AS percent
FROM games
WHERE game_power IS NOT NULL
GROUP BY power
ORDER BY power
;
