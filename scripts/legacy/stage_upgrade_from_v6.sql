-- alembic_version
alter table alembic_version drop constraint if exists alembic_version_pkc;
drop index if exists alembic_version_pkc;
alter table alembic_version rename to old_alembic_version;

-- guilds
create table migrate_guilds as
select
    guild_xid as xid,
    created_at,
    created_at as updated_at,
    cached_name as name,
    smotd as motd,
    case
        when links = 'public' then true
        else false
    end as show_links,
    create_voice as voice_create,
    false as show_points,
    prefix as legacy_prefix
from servers;
alter table servers rename to old_servers;

-- channels
create table migrate_channels as
select
    channel_xid as xid,
    created_at,
    updated_at,
    guild_xid,
    cached_name as name,
    coalesce(default_size, 4) as default_seats,
    false as auto_verify,
    false as unverified_only,
    require_verification as verified_only
from channel_settings;
update migrate_channels
    set unverified_only = true
    where xid in (select channel_xid from unverified_only_channels);
update migrate_channels
    set auto_verify = true
    where xid in (select channel_xid from auto_verify_channels);
alter table channel_settings rename to old_channel_settings;
alter table unverified_only_channels rename to old_unverified_only_channels;
alter table auto_verify_channels rename to old_auto_verify_channels;

-- games
create table migrate_games as
select
    games.id,
    games.created_at,
    games.updated_at,
    case
        when games.status = 'pending' then null
        when games.status = 'started' then games.updated_at
    end as started_at,
    games.guild_xid,
    games.channel_xid,
    games.message_xid,
    games.voice_channel_xid as voice_xid,
    games.size as seats,
    case
        when games.status = 'pending' then 1
        when games.status = 'started' then 2
    end as status,
    1 as format,
    games.url as spelltable_link,
    games.voice_channel_invite as voice_invite_link
from games
inner join old_channel_settings on
    games.channel_xid = old_channel_settings.channel_xid
where
    (games.status = 'pending' or games.status = 'started') and
    games.channel_xid is not null;
alter table games rename to old_games;

-- users
create table migrate_users as
select
    xid,
    created_at,
    updated_at,
    coalesce(cached_name, '') as name,
    banned,
    null::int as game_id
from users;
alter table users rename to old_users;

-- plays
create table migrate_plays as
select
    plays.user_xid,
    plays.game_id,
    user_points.points
from plays
left join user_points on
    plays.user_xid = user_points.user_xid and
    plays.game_id = user_points.game_id
inner join migrate_games on
    plays.game_id = migrate_games.id;
alter table plays rename to old_plays;
alter table user_points rename to old_user_points;

-- verify
create table migrate_verify as
select
    guild_xid,
    user_xid,
    verified
from user_server_settings;
alter table user_server_settings rename to old_user_server_settings;

-- watches
create table migrate_watches as
select
    guild_xid,
    user_xid,
    note
from watched_users;
alter table watched_users rename to old_watched_users;

-- blocks
create table migrate_blocks as
select
    user_xid,
    blocked_user_xid
from users_blocks;
alter table users_blocks rename to old_users_blocks;

-- guild_awards
create table migrate_guild_awards as
select
    id,
    guild_xid,
    count,
    repeating,
    role,
    message
from awards;
alter table awards rename to old_awards;

-- user_awards
create table migrate_user_awards as
select
    user_xid,
    guild_xid,
    current_award_id as guild_award_id
from user_awards;
alter table user_awards rename to old_user_awards;

-- unused tables
alter table tags rename to old_tags;
alter table games_tags rename to old_games_tags;
alter table teams rename to old_teams;
alter table reports rename to old_reports;
alter table channels rename to old_channels;
alter table events rename to old_events;
alter table pending_games rename to old_pending_games;
alter table metrics rename to old_metrics;

-- drop constraints
alter table old_auto_verify_channels drop constraint if exists auto_verify_channels_pkey cascade;
alter table old_awards drop constraint if exists awards_pkey cascade;
alter table old_channel_settings drop constraint if exists channel_settings_pkey cascade;
alter table old_channels drop constraint if exists channels_pkey cascade;
alter table old_events drop constraint if exists events_pkey cascade;
alter table old_games_tags drop constraint if exists game_tag_pk cascade;
alter table old_games drop constraint if exists games_pkey cascade;
alter table old_metrics drop constraint if exists metrics_pkey cascade;
alter table old_plays drop constraint if exists plays_pkey cascade;
alter table old_reports drop constraint if exists reports_pkey cascade;
alter table old_servers drop constraint if exists servers_pkey cascade;
alter table old_tags drop constraint if exists tags_pkey cascade;
alter table old_teams drop constraint if exists teams_pkey cascade;
alter table old_unverified_only_channels drop constraint if exists unverified_only_channels_pkey cascade;
alter table old_user_awards drop constraint if exists user_awards_pkey cascade;
alter table old_user_points drop constraint if exists user_points_pkey cascade;
alter table old_user_server_settings drop constraint if exists user_server_settings_pkey cascade;
alter table old_watched_users drop constraint if exists watched_users_pkey cascade;
alter table old_plays drop constraint if exists plays_user_xid_fkey cascade;
alter table old_user_awards drop constraint if exists user_awards_user_xid_fkey cascade;
alter table old_user_points drop constraint if exists user_points_user_xid_fkey cascade;
alter table old_user_server_settings drop constraint if exists user_server_settings_user_xid_fkey cascade;
alter table old_users_blocks drop constraint if exists users_blocks_blocked_user_xid_fkey cascade;
alter table old_users_blocks drop constraint if exists users_blocks_user_xid_fkey cascade;
alter table old_users_blocks drop constraint if exists uix_1;
alter table old_watched_users drop constraint if exists watched_users_user_xid_fkey cascade;
alter table old_users drop constraint if exists tmp_pkey;

-- drop indexes
drop index if exists auto_verify_channels_pkey cascade;
drop index if exists awards_pkey cascade;
drop index if exists channel_settings_pkey cascade;
drop index if exists channels_pkey cascade;
drop index if exists events_pkey cascade;
drop index if exists game_tag_pk cascade;
drop index if exists games_pkey cascade;
drop index if exists ix_auto_verify_channels_guild_xid cascade;
drop index if exists ix_channel_settings_guild_xid cascade;
drop index if exists ix_channels_guild_xid cascade;
drop index if exists ix_games_channel_xid cascade;
drop index if exists ix_games_created_at cascade;
drop index if exists ix_games_event_id cascade;
drop index if exists ix_games_guild_xid cascade;
drop index if exists ix_games_message_xid cascade;
drop index if exists ix_games_size cascade;
drop index if exists ix_games_status cascade;
drop index if exists ix_games_system cascade;
drop index if exists ix_games_updated_at cascade;
drop index if exists ix_games_voice_channel_xid cascade;
drop index if exists ix_metrics_channel_xid cascade;
drop index if exists ix_metrics_guild_xid cascade;
drop index if exists ix_metrics_kind cascade;
drop index if exists ix_metrics_user_xid cascade;
drop index if exists ix_reports_game_id cascade;
drop index if exists ix_teams_guild_xid cascade;
drop index if exists ix_unverified_only_channels_guild_xid cascade;
drop index if exists ix_user_awards_guild_xid cascade;
drop index if exists ix_user_awards_user_xid cascade;
drop index if exists ix_users_blocks_blocked_user_xid cascade;
drop index if exists ix_users_blocks_user_xid cascade;
drop index if exists ix_users_game_id;
drop index if exists metrics_pkey cascade;
drop index if exists plays_pkey cascade;
drop index if exists reports_pkey cascade;
drop index if exists servers_pkey cascade;
drop index if exists tags_pkey cascade;
drop index if exists teams_pkey cascade;
drop index if exists tmp_pkey cascade;
drop index if exists uix_1 cascade;
drop index if exists unverified_only_channels_pkey cascade;
drop index if exists user_awards_pkey cascade;
drop index if exists user_points_pkey cascade;
drop index if exists user_server_settings_pkey cascade;
drop index if exists watched_users_pkey cascade;

-- drop sequences
drop sequence if exists auto_verify_channels_channel_xid_seq cascade;
drop sequence if exists awards_id_seq cascade;
drop sequence if exists channel_settings_channel_xid_seq cascade;
drop sequence if exists channels_channel_xid_seq cascade;
drop sequence if exists events_id_seq cascade;
drop sequence if exists games_id_seq cascade;
drop sequence if exists metrics_id_seq cascade;
drop sequence if exists reports_id_seq cascade;
drop sequence if exists servers_guild_xid_seq cascade;
drop sequence if exists tags_id_seq cascade;
drop sequence if exists teams_id_seq cascade;
drop sequence if exists tmp_xid_seq cascade;
drop sequence if exists unverified_only_channels_channel_xid_seq cascade;
