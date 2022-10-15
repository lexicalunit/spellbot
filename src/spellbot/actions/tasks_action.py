from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator

from dateutil import tz
from ddtrace import tracer
from discord.channel import VoiceChannel

from .. import SpellBot
from ..database import db_session_manager, rollback_session
from ..metrics import add_span_error, setup_ignored_errors
from ..operations import (
    bot_can_delete_channel,
    safe_delete_channel,
    safe_delete_message,
    safe_fetch_text_channel,
    safe_get_partial_message,
    safe_update_embed,
)
from ..services import GamesService, ServicesRegistry
from ..settings import Settings
from .base_action import handle_exception

settings = Settings()
logger = logging.getLogger(__name__)


class VoiceChannelFilterer:
    def __init__(self, games: GamesService):
        self.games = games
        grace_delta = timedelta(minutes=settings.VOICE_GRACE_PERIOD_M)
        grace_time_ago = datetime.utcnow() - grace_delta
        self.grace_time_ago = grace_time_ago.replace(tzinfo=tz.UTC)
        age_limit_delta = timedelta(hours=settings.VOICE_AGE_LIMIT_H)
        age_limit_ago = datetime.utcnow() - age_limit_delta
        self.age_limit_ago = age_limit_ago.replace(tzinfo=tz.UTC)

    async def filter(self, voice_channels: list[VoiceChannel]) -> list[VoiceChannel]:
        channels: list[VoiceChannel] = []

        for channel in voice_channels:
            logger.info("considering channel %s(%s)", channel.name, channel.id)
            occupied = bool(channel.voice_states.keys())
            channel_created_at = channel.created_at.replace(tzinfo=tz.UTC)

            if channel_created_at > self.grace_time_ago:
                logger.info("channel is in grace period")
                continue

            if occupied and channel_created_at > self.age_limit_ago:
                logger.info("channel is occupied")
                continue

            if not bot_can_delete_channel(channel):
                logger.info("no permissions to delete channel (%s)", channel.id)
                continue

            if re.match(r"\AGame-SB\d+\Z", channel.name):
                logger.info("channel matches name format, adding to delete list")
                channels.append(channel)
                continue

            logger.info("looking for matching game in database")
            found = await self.games.select_by_voice_xid(channel.id)
            if found:
                logger.info("matching game found, adding to delete list")
                channels.append(channel)

        return channels


class TasksAction:
    def __init__(self, bot: SpellBot):
        self.bot = bot
        self.services = ServicesRegistry()

    @classmethod
    @asynccontextmanager
    async def create(cls, bot: SpellBot) -> AsyncGenerator[TasksAction, None]:
        action = cls(bot)
        with tracer.trace(name=f"spellbot.interactions.{cls.__name__}.create") as span:
            setup_ignored_errors(span)
            async with db_session_manager():
                try:
                    yield action
                except Exception as ex:  # pragma: no cover
                    await handle_exception(ex)

    async def cleanup_old_voice_channels(self):
        logger.info("starting task cleanup_old_voice_channels")
        try:
            channels = await self.gather_channels()
            await self.delete_channels(channels)
        except BaseException as e:  # Catch EVERYTHING so tasks don't die
            add_span_error(e)
            logger.exception("error: exception in background task: %s", e)
            await rollback_session()

    async def gather_channels(self) -> list[VoiceChannel]:
        channels: list[VoiceChannel] = []
        active_guild_xids = set(g.id for g in self.bot.guilds)
        channel_filterer = VoiceChannelFilterer(self.services.games)

        for guild_xid in await self.services.guilds.voiced():
            await self.services.guilds.select(guild_xid)
            guild_name = await self.services.guilds.current_name()
            logger.info("looking in guild %s(%s)", guild_name, guild_xid)
            prefixes = await self.services.guilds.voice_category_prefixes()

            if guild_xid not in active_guild_xids:
                logger.warning("guild is not active")
                continue

            guild = self.bot.get_guild(guild_xid)
            if not guild:
                logger.info("could not get guild from discord.py cache")
                continue

            voice_categories = filter(
                lambda c, ps=prefixes: any(c.name.startswith(prefix) for prefix in ps),
                guild.categories,
            )
            for category in voice_categories:
                logger.info("looking in category %s", category.name)
                voice_channels = await channel_filterer.filter(category.voice_channels)
                channels.extend(voice_channels)

        return channels

    async def delete_channels(self, channels: list[VoiceChannel]):
        batch = 0
        for channel in sorted(channels, key=lambda c: c.created_at):
            logger.info("deleting channel %s(%s)", channel.name, channel.id)
            await safe_delete_channel(channel, channel.guild.id)
            await asyncio.sleep(5)

            # Try to avoid rate limiting by the Discord API
            batch += 1
            if batch > settings.VOICE_CLEANUP_BATCH:
                remaining = len(channels) - settings.VOICE_CLEANUP_BATCH
                logger.info("batch limit reached, %s channels remain", remaining)
                break

    async def expire_inactive_games(self):
        logger.info("starting task expire_inactive_games")
        try:
            games = await self.services.games.inactive_games()
            await self.expire_games(games)
        except BaseException as e:  # Catch EVERYTHING so tasks don't die
            add_span_error(e)
            logger.exception("error: exception in background task: %s", e)
            await rollback_session()

    async def expire_games(self, games: list[dict[str, Any]]):
        batch = 0
        for game in games:
            game_id = game["id"]
            logger.info("expiring game %s...", game_id)
            await self.services.games.delete_games([game_id])
            await self.expire_game(game)

            batch += 1
            if batch >= 5:
                await asyncio.sleep(5)
                batch = 0
            else:
                await asyncio.sleep(1)

    async def expire_game(self, game: dict[str, Any]):
        message_xid = game["message_xid"]
        if message_xid is None:
            return

        guild_xid = game["guild_xid"]
        channel_xid = game["channel_xid"]
        chan = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)
        if not chan:
            return

        if not (post := safe_get_partial_message(chan, guild_xid, message_xid)):
            return

        channel_data = await self.services.channels.select(channel_xid)
        if channel_data["delete_expired"]:
            await safe_delete_message(post)
        else:
            await safe_update_embed(
                post,
                content="Sorry, this game was expired due to inactivity.",
                embed=None,
                view=None,
            )
