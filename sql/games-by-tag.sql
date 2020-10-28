SELECT
    DISTINCT(LOWER(name)) as tag
    , COUNT(1) as games
FROM tags
JOIN games_tags ON games_tags.tag_id = tags.id
JOIN games ON games.id = games_tags.game_id
GROUP BY tag
ORDER BY games DESC
LIMIT 10
;
