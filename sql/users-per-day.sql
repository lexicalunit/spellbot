SELECT
    DATE(users.created_at) AS day
    , COUNT(users.xid) AS users
FROM users
GROUP BY day
ORDER BY day
;
