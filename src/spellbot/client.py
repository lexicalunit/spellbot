import asyncio
import logging
import traceback
from asyncio import AbstractEventLoop as Loop
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional
from uuid import uuid4

import discord
from asgiref.sync import sync_to_async
from discord.ext.commands import Bot, errors
from discord_slash import SlashCommand, context
from expiringdict import ExpiringDict

from spellbot.database import (
    db_session_manager,
    get_legacy_prefixes,
    initialize_connection,
)
from spellbot.errors import SpellbotAdminOnly, UserBannedError
from spellbot.operations import safe_send_channel
from spellbot.services.channels import ChannelsService
from spellbot.services.guilds import GuildsService
from spellbot.services.verifies import VerifiesService
from spellbot.settings import Settings
from spellbot.spelltable import generate_link
from spellbot.utils import user_can_moderate

logger = logging.getLogger(__name__)


@sync_to_async
def begin_session():
    from spellbot.database import DatabaseSession, db_session_maker

    db_session = db_session_maker()
    DatabaseSession.set(db_session)  # type: ignore


class SpellBot(Bot):
    slash: SlashCommand

    def __init__(
        self,
        loop: Optional[Loop] = None,
        mock_games: bool = False,
    ):
        self.settings = Settings()
        intents = discord.Intents().default()
        intents.members = True  # pylint: disable=E0237
        intents.messages = True  # pylint: disable=E0237
        super().__init__(
            command_prefix="!",
            help_command=None,
            loop=loop,
            intents=intents,
        )
        self.mock_games = mock_games
        self.legacy_prefix_cache = defaultdict(lambda: "!")
        self.channel_locks = ExpiringDict(max_len=100, max_age_seconds=3600)  # 1 hr

    @asynccontextmanager
    async def channel_lock(self, channel_xid: int) -> AsyncGenerator[None, None]:
        if not self.channel_locks.get(channel_xid):
            self.channel_locks[channel_xid] = asyncio.Lock()
        async with self.channel_locks[channel_xid]:  # type: ignore
            yield

    async def create_spelltable_link(self) -> Optional[str]:
        if self.mock_games:
            return f"http://exmaple.com/game/{uuid4()}"
        return await generate_link()

    async def handle_errors(self, ctx: context.InteractionContext, ex: Exception):
        if isinstance(ex, errors.NoPrivateMessage):
            return await safe_send_channel(
                ctx,
                "This command is not supported via Direct Message.",
                hidden=True,
            )
        if isinstance(ex, SpellbotAdminOnly):
            return await safe_send_channel(
                ctx,
                "You do not have permission to do that.",
                hidden=True,
            )
        if isinstance(ex, UserBannedError):
            return await safe_send_channel(
                ctx,
                "You have been banned from using SpellBot.",
                hidden=True,
            )

        ref = (
            f"command `{ctx.name}`"
            if isinstance(ctx, context.SlashContext)
            else f"component `{ctx.custom_id}`"
            if isinstance(ctx, context.ComponentContext)
            else f"interaction `{ctx.interaction_id}`"
        )
        logger.error(
            "error: unhandled exception in %s: %s: %s",
            ref,
            ex.__class__.__name__,
            ex,
        )
        traceback.print_tb(ex.__traceback__)

    async def on_component_callback_error(
        self,
        ctx: context.ComponentContext,
        ex: Exception,
    ):
        return await self.handle_errors(ctx, ex)

    async def on_slash_command_error(self, ctx: context.SlashContext, ex: Exception):
        return await self.handle_errors(ctx, ex)

    async def on_message(self, message: discord.Message):
        if not message.guild or not hasattr(message.guild, "id"):
            return await super().on_message(message)  # handle DMs normally
        if (
            not hasattr(message.channel, "type")
            or message.channel.type != discord.ChannelType.text
        ):
            return  # ignore everything else, except messages in text channels...
        if message.flags.value & 64:
            return  # message is hidden, ignore it

        async with db_session_manager():
            await self.handle_verification(message)

        guild_xid = message.guild.id  # type: ignore
        if message.content.startswith(self.legacy_prefix_cache[guild_xid]):
            try:
                settings = Settings()
                embed = discord.Embed()
                embed.set_thumbnail(url=settings.ICO_URL)
                embed.description = (
                    "SpellBot uses slash commands now. Just type `/` to see the list"
                    " of supported commands! It may take up to one hour for these"
                    " commands to appear for the first time. Also note that"
                    " SpellBot's invite link has changed. Your server admin may need"
                    " to re-invite the bot using the [updated invite link]"
                    f"({settings.BOT_INVITE_LINK}) if slash commands do not show up"
                    " after one hour."
                )
                embed.color = settings.EMBED_COLOR
                await message.reply(embed=embed)
            except Exception as ex:
                logger.warning("warning: %s", ex, exc_info=True)

    async def handle_verification(self, message: discord.Message):
        # To verify users we need their user id, so just give up if it's not available
        if not hasattr(message.author, "id"):
            return
        message_author_xid = message.author.id  # type: ignore
        verified: Optional[bool] = None
        guilds = GuildsService()
        await guilds.upsert(message.guild)
        channels = ChannelsService()
        await channels.upsert(message.channel)
        if await channels.should_auto_verify():
            verified = True
        verify = VerifiesService()
        assert message.guild
        guild: discord.Guild = message.guild  # type: ignore
        await verify.upsert(guild.id, message_author_xid, verified)
        if not user_can_moderate(message.author, guild, message.channel):
            user_is_verified = await verify.is_verified()
            if user_is_verified and await channels.unverified_only():
                await message.delete()
            if not user_is_verified and await channels.verified_only():
                await message.delete()


async def bot_connection(bot):
    logger.info("initializing database connection...")
    await initialize_connection("spellbot-bot")

    async with db_session_manager():
        logger.info("building legacy command prefix cache...")
        db_legacy_prefixes = await get_legacy_prefixes()
        bot.legacy_prefix_cache.update(db_legacy_prefixes)


def build_bot(
    loop: Optional[Loop] = None,
    mock_games: bool = False,
    force_sync_commands: bool = False,
    clean_commands: bool = False,
    create_connection: bool = True,
) -> SpellBot:
    bot = SpellBot(loop=loop, mock_games=mock_games)

    # setup slash commands extension
    debug_guild: Optional[int] = None
    if bot.settings.DEBUG_GUILD:  # pragma: no cover
        debug_guild = int(bot.settings.DEBUG_GUILD)
        logger.info("using debug guild: %s", debug_guild)
    bot.slash = SlashCommand(
        bot,
        debug_guild=debug_guild,
        sync_commands=force_sync_commands,
        delete_from_unused_guilds=clean_commands,
    )

    if create_connection:  # pragma: no cover
        # In tests we create the connection using fixtures.
        bot.loop.run_until_complete(bot_connection(bot))

    # load all cog extensions
    from spellbot.cogs import load_all_cogs

    load_all_cogs(bot)
    commands = (key for key in bot.slash.commands if key != "context")
    logger.info("loaded commands: %s", ", ".join(commands))

    return bot
