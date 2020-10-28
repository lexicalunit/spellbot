SELECT
    teams.name AS team
    , SUM(user_points.points) AS points
FROM users
JOIN user_teams ON user_teams.user_xid = users.xid
JOIN user_points ON user_points.user_xid = users.xid
JOIN teams ON teams.id = user_teams.team_id
GROUP BY team
;
