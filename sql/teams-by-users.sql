SELECT
    DISTINCT(LOWER(name)) as team
    , COUNT(1) as members
    , ROUND(COUNT(1) * 1.0 / (
        SELECT COUNT(1)
        FROM user_teams
    ) * 100.0) AS percent
FROM teams
JOIN user_teams ON user_teams.team_id = teams.id
JOIN users ON users.xid = user_teams.user_xid
GROUP BY team
ORDER BY members DESC
LIMIT 10
;
