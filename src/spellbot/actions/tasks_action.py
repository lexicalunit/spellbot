from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import discord
from dateutil import tz
from ddtrace.trace import tracer

from spellbot import services
from spellbot.database import db_session_manager, rollback_session
from spellbot.metrics import (
    add_span_error,
    add_span_request_id,
    generate_request_id,
    setup_ignored_errors,
)
from spellbot.operations import (
    bot_can_delete_channel,
    safe_delete_channel,
    safe_delete_message,
    safe_fetch_text_channel,
    safe_fetch_user,
    safe_get_partial_message,
    safe_send_user,
    safe_update_embed,
)
from spellbot.settings import settings

from .base_action import handle_exception

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from discord.channel import VoiceChannel

    from spellbot import SpellBot
    from spellbot.data import GameData

logger = logging.getLogger(__name__)


class VoiceChannelFilterer:
    def __init__(self) -> None:
        grace_delta = timedelta(minutes=settings.VOICE_GRACE_PERIOD_M)
        grace_time_ago = datetime.now(tz=UTC) - grace_delta
        self.grace_time_ago = grace_time_ago.replace(tzinfo=tz.UTC)
        age_limit_delta = timedelta(hours=settings.VOICE_AGE_LIMIT_H)
        age_limit_ago = datetime.now(tz=UTC) - age_limit_delta
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
            found = await services.games.get_by_voice_xid(channel.id)
            if found:
                logger.info("matching game found, adding to delete list")
                channels.append(channel)

        return channels


class TasksAction:
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @classmethod
    @asynccontextmanager
    async def create(cls, bot: SpellBot) -> AsyncGenerator[TasksAction]:
        action = cls(bot)
        with tracer.trace(name=f"spellbot.interactions.{cls.__name__}.create") as span:
            setup_ignored_errors(span)
            add_span_request_id(generate_request_id())
            async with db_session_manager():
                try:
                    yield action
                except Exception as ex:  # pragma: no cover
                    await handle_exception(ex)

    async def cleanup_old_voice_channels(self) -> None:
        logger.info("starting task cleanup_old_voice_channels")
        try:
            channels = await self.gather_channels()
            await self.delete_channels(channels)
        except BaseException as e:  # Catch EVERYTHING so tasks don't die
            add_span_error(e)
            logger.exception("error: exception in background task")
            await rollback_session()

    async def gather_channels(self) -> list[VoiceChannel]:
        channels: list[VoiceChannel] = []
        active_guild_xids = {g.id for g in self.bot.guilds}
        channel_filterer = VoiceChannelFilterer()

        for guild_xid in await services.guilds.voiced():
            guild_data = await services.guilds.get(guild_xid)
            guild_name = guild_data.name if guild_data else ""
            logger.info("looking in guild %s(%s)", guild_name, guild_xid)
            prefixes = await services.guilds.voice_category_prefixes(guild_xid)

            if guild_xid not in active_guild_xids:
                logger.info("guild is not active")
                await services.guilds.set_active(guild_xid, False)
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

    async def delete_channels(self, channels: list[VoiceChannel]) -> None:
        for batch, channel in enumerate(sorted(channels, key=lambda c: c.created_at)):
            logger.info("deleting channel %s(%s)", channel.name, channel.id)
            await safe_delete_channel(channel, channel.guild.id)
            await asyncio.sleep(5)

            # Try to avoid rate limiting by the Discord API
            if batch + 1 > settings.VOICE_CLEANUP_BATCH:
                remaining = len(channels) - settings.VOICE_CLEANUP_BATCH
                logger.info("batch limit reached, %s channels remain", remaining)
                break

    async def expire_inactive_games(self) -> None:
        logger.info("starting task expire_inactive_games")
        try:
            games = await services.games.inactive_games()
            await self.expire_games(games)
        except BaseException as e:  # Catch EVERYTHING so tasks don't die
            add_span_error(e)
            logger.exception("error: exception in background task")
            await rollback_session()

    async def expire_games(self, game_data_list: list[GameData]) -> None:
        batch = 0
        for game_data in game_data_list:
            logger.info("expiring game %s...", game_data.id)
            dequeued = await services.games.delete_games([game_data.id])
            await self.expire_game(game_data, dequeued)

            batch += 1
            if batch >= 5:  # pragma: no cover
                await asyncio.sleep(5)
                batch = 0
            else:
                await asyncio.sleep(1)

    async def expire_game(self, game_data: GameData, dequeued: int) -> None:
        for post_data in game_data.posts:
            guild_xid = post_data.guild_xid
            channel_xid = post_data.channel_xid
            message_xid = post_data.message_xid

            chan = await safe_fetch_text_channel(self.bot, guild_xid, channel_xid)
            if not chan:
                continue

            post = safe_get_partial_message(chan, guild_xid, message_xid)
            if not post:
                continue

            channel_data = await services.channels.select(channel_xid)
            if not dequeued or (channel_data and channel_data.delete_expired):
                await safe_delete_message(post)
            else:
                await safe_update_embed(
                    post,
                    content="Sorry, this game was expired due to inactivity.",
                    embed=None,
                    view=None,
                )

    async def patreon_sync(self) -> None:
        logger.info("starting task patreon_sync")
        self.bot.supporters = await services.patreon.supporters()

    async def notify_pending_games(self) -> None:
        logger.info("starting task notify_pending_games")
        try:
            games = await services.games.games_pending_notification()
            await self.notify_games(games)
        except BaseException as e:  # Catch EVERYTHING so tasks don't die
            add_span_error(e)
            logger.exception("error: exception in background task")
            await rollback_session()

    async def notify_games(self, game_data_list: list[GameData]) -> None:
        for game_data in game_data_list:
            logger.info("notifying for game %s...", game_data.id)
            await self.notify_game(game_data)
            await services.alerts.mark_notified(game_data.id)
            await asyncio.sleep(1)

    async def notify_game(self, game_data: GameData) -> None:
        user_xids = await services.alerts.find_matching_user_xids(
            guild_xid=game_data.guild_xid,
            format=game_data.format,
            bracket=game_data.bracket,
            channel_xid=game_data.channel_xid,
        )
        if not user_xids:
            return
        embed = self.build_notification_embed(game_data)
        for user_xid in user_xids:
            user = await safe_fetch_user(self.bot, user_xid)
            if not user:
                continue
            await safe_send_user(user, embed=embed, kind="notification")

    def build_notification_embed(self, game_data: GameData) -> discord.Embed:
        guild_name = game_data.guild.name or "this server"
        channel_name = game_data.channel.name or "a channel"
        remaining = max(game_data.seats - len(game_data.players), 0)
        title = f"A {game_data.format_name} game is looking for players"
        description_lines = [
            f"A pending game in **{guild_name}** matches your notification preferences.",
            f"Channel: <#{game_data.channel_xid}>",
            f"Open seats: **{remaining}** of {game_data.seats}",
        ]
        if game_data.bracket != 0:
            description_lines.append(f"Bracket: {game_data.bracket_title}")
        jump_link = game_data.jump_links.get(game_data.guild_xid)
        if jump_link:
            description_lines.append(f"[Jump to the game post]({jump_link})")
        prefs_link = f"{settings.API_BASE_URL}/queues/g/{game_data.guild_xid}"
        description_lines.append(
            f"You're receiving this because you set notification preferences for "
            f"#{channel_name}. [Adjust your preferences]({prefs_link}).",
        )
        return discord.Embed(
            title=title,
            description="\n".join(description_lines),
            color=discord.Color(settings.INFO_EMBED_COLOR),
        )
