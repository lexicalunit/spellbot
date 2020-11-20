SELECT
    teams.name AS team
    , SUM(user_points.points) AS points
FROM users
JOIN user_server_settings ON user_server_settings.user_xid = users.xid
JOIN user_points ON user_points.user_xid = users.xid
JOIN teams ON teams.id = user_server_settings.team_id
GROUP BY team
;
