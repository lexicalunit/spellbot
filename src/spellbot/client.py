from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import uuid4

import discord
from ddtrace import tracer
from discord.ext.commands import AutoShardedBot, CommandError, CommandNotFound, Context

from .database import db_session_manager, initialize_connection
from .metrics import setup_ignored_errors, setup_metrics
from .operations import safe_delete_message
from .services import ChannelsService, GamesService, GuildsService, VerifiesService
from .settings import settings
from .spelltable import generate_link
from .utils import user_can_moderate

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


class SpellBot(AutoShardedBot):
    def __init__(
        self,
        mock_games: bool = False,
        create_connection: bool = True,
    ) -> None:
        intents = discord.Intents().default()
        intents.members = True
        intents.message_content = True
        intents.messages = True
        logger.info("intents.value: %s", intents.value)
        super().__init__(
            command_prefix="!",
            help_command=None,
            intents=intents,
            application_id=settings.BOT_APPLICATION_ID,
        )
        self.mock_games = mock_games
        self.create_connection = create_connection
        self.critical_lock = asyncio.Lock()

    async def on_ready(self) -> None:  # pragma: no cover
        logger.info("client ready")

    async def on_shard_ready(self, shard_id: int) -> None:  # pragma: no cover
        logger.info("shard %s ready", shard_id)

    async def setup_hook(self) -> None:  # pragma: no cover
        # Note: In tests we create the connection using fixtures.
        if self.create_connection:  # pragma: no cover
            logger.info("initializing database connection...")
            await initialize_connection("spellbot-bot")

        # register persistent views
        from .views import PendingGameView, SetupView, StartedGameView, StartedGameViewWithConfirm

        self.add_view(PendingGameView(self))
        self.add_view(SetupView(self))
        self.add_view(StartedGameView(self))
        self.add_view(StartedGameViewWithConfirm(self))

        # load all cog extensions and application commands
        from .utils import load_extensions

        await load_extensions(self)

    @asynccontextmanager
    async def guild_lock(self, guild_xid: int) -> AsyncGenerator[None, None]:
        # We used to have a lock per guild, but now that users can join games in
        # multiple guilds at the same time, we need to have a global lock for the
        # critical paths related to joining and leaving games. That is why we're
        # ignoring the passed in guild_xid parameter. In the future this could be
        # refactored to use a more fine-grained locking mechanism, or else remove
        # the unused parameter.
        async with self.critical_lock:
            yield

    @tracer.wrap()
    async def create_spelltable_link(self) -> str | None:
        if self.mock_games:
            return f"http://exmaple.com/game/{uuid4()}"
        return await generate_link()

    @tracer.wrap(name="interaction", resource="on_message")
    async def on_message(
        self,
        message: discord.Message,
    ) -> None:
        span = tracer.current_span()
        if span:  # pragma: no cover
            setup_ignored_errors(span)

        # handle DMs normally
        if not message.guild or not hasattr(message.guild, "id"):
            return await super().on_message(message)
        if span:  # pragma: no cover
            span.set_tag("guild_id", message.guild.id)

        # ignore everything except messages in text channels
        if not hasattr(message.channel, "type") or message.channel.type != discord.ChannelType.text:
            return None
        if span:  # pragma: no cover
            span.set_tag("channel_id", message.channel.id)

        # ignore hidden/ephemeral messages
        if message.flags.value & 64:
            return None

        # to verify users we need their user id
        if not hasattr(message.author, "id"):
            return None

        message_author_xid = message.author.id
        if span:
            span.set_tag("author_id", message_author_xid)

        # don't try to verify the bot itself
        if self.user and message_author_xid == self.user.id:  # pragma: no cover
            return None

        async with db_session_manager():
            await self.handle_verification(message)
            return None

    @tracer.wrap(name="interaction", resource="on_message_delete")
    async def on_message_delete(self, message: discord.Message) -> None:
        message_xid: int | None = getattr(message, "id", None)
        if not message_xid:
            return
        async with db_session_manager():
            await self.handle_message_deleted(message)

    async def on_command_error(
        self,
        context: Context[SpellBot],
        exception: CommandError,
    ) -> None:
        if isinstance(exception, CommandNotFound):
            return None
        return await super().on_command_error(context, exception)

    @tracer.wrap()
    async def handle_verification(self, message: discord.Message) -> None:
        message_author_xid = message.author.id
        verified: bool | None = None
        guilds = GuildsService()
        assert message.guild is not None
        await guilds.upsert(message.guild)
        channels = ChannelsService()
        channel_data = await channels.upsert(message.channel)
        if channel_data["auto_verify"]:
            verified = True
        verify = VerifiesService()
        assert message.guild
        guild: discord.Guild = message.guild
        await verify.upsert(guild.id, message_author_xid, verified)
        if not user_can_moderate(message.author, guild, message.channel):
            user_is_verified = await verify.is_verified()
            if user_is_verified and channel_data["unverified_only"]:
                await safe_delete_message(message)
            if not user_is_verified and channel_data["verified_only"]:
                await safe_delete_message(message)

    @tracer.wrap()
    async def handle_message_deleted(self, message: discord.Message) -> None:
        games = GamesService()
        data = await games.select_by_message_xid(message.id)
        if not data:
            return
        game_id = data["id"]
        logger.info("Game %s was deleted manually.", game_id)
        if not data["started_at"]:  # someone deleted a pending game
            await games.delete_games([game_id])


def build_bot(mock_games: bool = False, create_connection: bool = True) -> SpellBot:
    bot = SpellBot(mock_games=mock_games, create_connection=create_connection)
    setup_metrics()
    return bot
