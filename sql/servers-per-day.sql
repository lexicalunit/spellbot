SELECT
    DATE(servers.created_at) AS day
    , COUNT(servers.guild_xid) AS count
FROM servers
GROUP BY day
ORDER BY day
;
