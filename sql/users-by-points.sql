SELECT
    DISTINCT(users.cached_name) AS name
    , SUM(user_points.points) AS points
FROM users
JOIN user_points on user_points.user_xid = users.xid
WHERE points > 0
GROUP BY name
ORDER BY points DESC
LIMIT 10
;
