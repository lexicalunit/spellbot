# pylint: disable=wrong-import-order

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional, Type, TypeVar, cast

import discord
from asgiref.sync import sync_to_async
from discord_slash.context import InteractionContext

from .. import SpellBot
from ..database import DatabaseSession, db_session_manager
from ..errors import SpellbotAdminOnly, UserBannedError
from ..services import ServicesRegistry

logger = logging.getLogger(__name__)

InteractionType = TypeVar("InteractionType", bound="BaseInteraction")


class BaseInteraction:
    bot: SpellBot
    services: ServicesRegistry
    ctx: Optional[InteractionContext]
    member: Optional[discord.Member]
    guild: Optional[discord.Guild]
    channel: Optional[discord.TextChannel]
    channel_data: dict

    def __init__(self, bot: SpellBot, ctx: Optional[InteractionContext] = None):
        self.bot = bot
        self.services = ServicesRegistry()
        self.ctx = ctx
        if self.ctx:
            self.member = cast(discord.Member, self.ctx.author)
            self.guild = cast(discord.Guild, self.ctx.guild)
            self.channel = cast(discord.TextChannel, self.ctx.channel)

    @sync_to_async
    def handle_exception(self, ex):
        if isinstance(ex, (SpellbotAdminOnly, UserBannedError)):
            raise ex
        logger.exception(
            "error: rolling back database session due to unhandled exception: %s: %s",
            ex.__class__.__name__,
            ex,
        )
        DatabaseSession.rollback()
        raise ex

    async def upsert_request_objects(self):
        if hasattr(self, "guild") and self.guild:
            await self.services.guilds.upsert(self.guild)

        if hasattr(self, "channel") and self.channel:
            self.channel_data = await self.services.channels.upsert(self.channel)

        if hasattr(self, "member") and self.member:
            await self.services.users.upsert(self.member)

        if hasattr(self, "ctx") and self.ctx:
            if await self.services.users.is_banned(self.ctx.author_id):
                raise UserBannedError()

    @classmethod
    @asynccontextmanager
    async def create(
        cls: Type[InteractionType],
        bot: SpellBot,
        ctx: Optional[InteractionContext] = None,
    ) -> AsyncGenerator[InteractionType, None]:
        interaction = cls(bot, ctx) if ctx else cls(bot)
        async with db_session_manager():
            try:
                await interaction.upsert_request_objects()
                yield interaction
            except Exception as ex:
                await interaction.handle_exception(ex)
