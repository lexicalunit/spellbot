from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import redis

if TYPE_CHECKING:  # pragma: no cover
    from spellbot import SpellBot

from spellbot.data import Game, Server, User
from spellbot.operations import safe_delete_channel, safe_fetch_channel

logger = logging.getLogger(__name__)


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
    logger.info("starting old voice channels cleanup task...")
    async with bot.session() as session:
        for game in Game.voiced(session):
            assert game.voice_channel_xid
            chan = await safe_fetch_channel(bot, game.voice_channel_xid, game.guild_xid)
            if not chan:
                game.voice_channel_xid = None  # type: ignore
                game.voice_channel_invite = None  # type: ignore
                continue

            empty_or_really_old = (
                not chan.voice_states.keys()  # type: ignore
                or datetime.utcnow() >= game.updated_at + timedelta(hours=7)
            )
            if empty_or_really_old:
                await safe_delete_channel(chan, game.guild_xid)
                game.voice_channel_xid = None  # type: ignore
                game.voice_channel_invite = None  # type: ignore
        session.commit()


async def cleanup_started_games(bot: SpellBot) -> None:
    """Culls games older than the given window of minutes."""
    logger.info("starting started games cleanup task...")
    async with bot.session() as session:
        games = session.query(Game).filter(Game.status == "started").all()
        for game in games:
            game.tags = []  # cascade delete tag associations
            session.delete(game)
        session.commit()


async def update_metrics(bot: SpellBot) -> None:
    if not bot.metrics_db:
        return

    logger.info("starting update metrics task...")
    async with bot.session() as session:
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
    {"interval": 3600, "function": update_metrics},  # 1 hour
    {"interval": 600, "function": cleanup_old_voice_channels},  # 10 minutes
    # Make cleanup_started_games manually triggered?
    # {"interval": 14400, "function": "cleanup_started_games"}, # 4 hours
]


def begin_background_tasks(bot: SpellBot) -> None:
    """Start up any periodic background tasks."""
    for task_spec in BACKROUND_TASK_SPECS:

        def task_context(spec: dict) -> None:
            INTERVAL = spec["interval"]

            async def task_runner() -> None:
                while True:
                    await spec["function"](bot)
                    await asyncio.sleep(INTERVAL)

            bot.loop.create_task(task_runner())

        task_context(task_spec)
