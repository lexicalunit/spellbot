insert into guilds select * from migrate_guilds;
insert into channels select * from migrate_channels;
insert into games select * from migrate_games;
select setval('games_id_seq', coalesce((select max(id)+1 from games), 1), false);
insert into users select * from migrate_users;
insert into plays select * from migrate_plays;
insert into verify select * from migrate_verify;
insert into watches select * from migrate_watches;
insert into blocks select * from migrate_blocks;
insert into guild_awards select * from migrate_guild_awards;
select setval('guild_awards_id_seq', coalesce((select max(id)+1 from guild_awards), 1), false);
insert into user_awards select * from migrate_user_awards;

drop table if exists migrate_guilds;
drop table if exists migrate_channels;
drop table if exists migrate_games;
drop table if exists migrate_users;
drop table if exists migrate_plays;
drop table if exists migrate_verify;
drop table if exists migrate_watches;
drop table if exists migrate_blocks;
drop table if exists migrate_guild_awards;
drop table if exists migrate_user_awards;

drop table old_metrics;
