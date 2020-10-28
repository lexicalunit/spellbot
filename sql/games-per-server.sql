SELECT
    servers.cached_name AS name
    , COUNT(games.id) AS games
FROM servers
JOIN games ON games.guild_xid = servers.guild_xid
WHERE games.status = 'started'
    AND servers.cached_name IS NOT NULL
GROUP BY name
ORDER BY games DESC
;
