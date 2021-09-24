from __future__ import annotations

import asyncio
import logging
from asyncio.tasks import Task
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, cast

import redis
from dateutil import tz
from more_itertools import random_permutation

from spellbot.constants import BATCH_LIMIT, REALLY_OLD_GAMES_HOURS, VOICE_CATEGORY_PREFIX

if TYPE_CHECKING:  # pragma: no cover
    from spellbot import SpellBot

from spellbot.data import Game, Server, User
from spellbot.operations import safe_delete_channel, safe_fetch_guild

logger = logging.getLogger(__name__)


def randomly(seq):
    for idx in random_permutation(range(len(seq))):
        yield seq[idx]


async def cleanup_expired_games(bot: SpellBot) -> None:
    """Culls games older than the given window of minutes."""
    logger.info("starting expired games cleanup task...")

    to_delete_args = []
    async with bot.session() as session:
        expired = Game.expired(session)
        for game in expired:
            if not game.is_expired():
                continue

            if game.guild_xid and game.channel_xid and game.message_xid:
                to_delete_args.append(
                    {
                        "guild_xid": game.guild_xid,
                        "channel_xid": game.channel_xid,
                        "message_xid": game.message_xid,
                    }
                )

            for user in game.users:
                # Make sure the user is still waiting and still in the
                # game that's being deleted, they could be in a new
                # game now due to how async processing works.
                if user.waiting and user.game_id == game.id:
                    user.game_id = None

            # cascade delete tag associations
            game.tags = []  # type: ignore
            session.delete(game)
        session.commit()

    for args in to_delete_args:
        async with bot.channel_lock(args["channel_xid"]):
            await bot.try_to_delete_message(**args)


async def cleanup_old_voice_channels(bot: SpellBot) -> None:
    """Checks for and deletes any bot created voice channels that are empty."""
    batch = 0
    grace_delta = timedelta(minutes=1)
    grace_time_ago = datetime.utcnow() - grace_delta
    grace_time_ago = grace_time_ago.replace(tzinfo=tz.UTC)
    age_limit_delta = timedelta(hours=REALLY_OLD_GAMES_HOURS)
    age_limit_ago = datetime.utcnow() - age_limit_delta
    age_limit_ago = age_limit_ago.replace(tzinfo=tz.UTC)
    async with bot.session() as session:
        for server in Server.voiced(session):
            logger.info(f"checking for categories in guild {server.guild_xid}...")
            guild = await safe_fetch_guild(bot, server.guild_xid)
            if not guild:
                continue
            voice_categories = filter(
                lambda c: c.name.startswith(VOICE_CATEGORY_PREFIX),
                guild.categories,
            )
            for category in voice_categories:
                logger.info(f"checking for channels in guild {guild.id}...")
                voice_channels = category.voice_channels
                for channel in voice_channels:
                    logger.info(f"considering channel {channel.id}...")
                    occupied = bool(channel.voice_states.keys())
                    channel_created_at = channel.created_at
                    if channel_created_at > grace_time_ago:
                        logger.info(f"channel {channel.id} is in grace period")
                        continue
                    elif not occupied or channel_created_at < age_limit_ago:
                        logger.info(f"deleting channel {channel.id}...")
                        game = (
                            session.query(Game)
                            .filter(Game.voice_channel_xid == channel.id)
                            .one_or_none()
                        )
                        if game:
                            game.voice_channel_xid = None  # type: ignore
                            game.voice_channel_invite = None  # type: ignore
                            session.commit()
                        await safe_delete_channel(channel, guild.id)

                        # Try to avoid rate limiting on the Discord API
                        batch += 1
                        if batch > BATCH_LIMIT:
                            return
                    else:
                        logger.info(f"channel {channel.id} is occupied")


async def cleanup_started_games(bot: SpellBot) -> None:
    """Culls games older than the given window of minutes."""
    logger.info("starting started games cleanup task...")
    async with bot.session() as session:
        games = session.query(Game).filter(Game.status == "started").all()
        for game in games:
            # cascade delete tag associations
            game.tags = []  # type: ignore
            session.delete(game)
        session.commit()


async def update_metrics(bot: SpellBot) -> None:
    if not bot.metrics_db:
        return

    logger.info("starting update metrics task...")
    async with bot.session() as session:
        active = len(bot.guilds)
        games = session.query(Game).filter(Game.status == "started").count()
        servers = session.query(Server).count()
        users = session.query(User).count()
        recent_games = Game.recent_metrics(session)
        recent_users = User.recent_metrics(session)
        recent_servers = Server.recent_metrics(session)
        recent_metrics = {
            **recent_games,
            **recent_users,
            **recent_servers,
        }
        try:
            bot.metrics_db.mset(
                {
                    "servers": servers,
                    "games": games,
                    "users": users,
                    "active": active,
                }
            )
            if recent_metrics:
                bot.metrics_db.mset(recent_metrics)
        except redis.exceptions.RedisError as e:
            logger.exception("redis error: %s", e)


async def update_average_wait_times(bot: SpellBot) -> None:
    logger.info("starting update average wait times task...")
    async with bot.session() as session:
        bot.average_wait_times = {}
        avgs = Game.average_wait_times(session)
        for avg in avgs:
            bot.average_wait_times[f"{avg[0]}-{avg[1]}"] = float(avg[2])


BACKROUND_TASK_SPECS = [
    {"interval": 120, "function": cleanup_expired_games},  # 2 minutes
    {"interval": 1800, "function": update_average_wait_times},  # 30 minutes
    {"interval": 1800, "function": update_metrics},  # 30 minutes
    {"interval": 3600, "function": cleanup_old_voice_channels},  # 1 hour
    # Make cleanup_started_games manually triggered?
    # {"interval": 14400, "function": "cleanup_started_games"}, # 4 hours
]


def begin_background_tasks(bot: SpellBot) -> List[Task]:
    """Start up any periodic background tasks."""
    jobs: List[Task] = []
    for task_spec in BACKROUND_TASK_SPECS:

        def task_context(spec: dict) -> Task:
            INTERVAL = spec["interval"]

            async def task_runner() -> None:
                while True:
                    try:
                        await spec["function"](bot)
                    except BaseException as e:
                        logger.exception("error: unhandled exception in task: %s", e)
                    finally:
                        await asyncio.sleep(INTERVAL)

            return cast(Task, bot.loop.create_task(task_runner()))

        jobs.append(task_context(task_spec))

    return jobs
