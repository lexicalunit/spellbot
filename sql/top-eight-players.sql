SELECT
    play_ranks.player
    , play_ranks.channel
    , play_ranks.player_rank as "rank"
    , play_ranks.plays
FROM (
    SELECT
        play_counts.player
        , play_counts.channel
        , play_counts.plays
        , ROW_NUMBER() OVER (PARTITION BY channel ORDER BY channel, plays DESC) AS player_rank
    FROM (
        SELECT
            users.cached_name as player
            , channel_settings.cached_name as channel
            , COUNT(plays.game_id) as plays
        FROM plays
        LEFT JOIN users
            ON plays.user_xid = users.xid
        LEFT JOIN games
            ON plays.game_id = games.id
        LEFT JOIN channel_settings
            ON games.channel_xid = channel_settings.channel_xid
        WHERE users.cached_name IS NOT NULL
            AND channel_settings.cached_name IS NOT NULL
            AND games.guild_xid = 304276578005942272 -- PlayEDH
        GROUP BY player, channel
    ) AS play_counts
) AS play_ranks
WHERE player_rank <= 8
;
