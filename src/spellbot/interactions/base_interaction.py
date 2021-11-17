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
from ..errors import (
    SpellBotError,
    UserBannedError,
    UserUnverifiedError,
    UserVerifiedError,
)
from ..services import ServicesRegistry, VerifiesService
from ..utils import user_can_moderate

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
        if isinstance(ex, SpellBotError):
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

        if self.should_do_verification():
            await self.handle_verification()

    async def handle_verification(self):
        assert self.guild
        assert self.ctx
        verified: Optional[bool] = None
        if self.channel_data["auto_verify"]:
            verified = True
        verify = VerifiesService()
        await verify.upsert(self.guild.id, self.ctx.author_id, verified)
        if not user_can_moderate(self.ctx.author, self.guild, self.channel):
            user_is_verified = await verify.is_verified()
            if user_is_verified and self.channel_data["unverified_only"]:
                raise UserVerifiedError()
            if not user_is_verified and self.channel_data["verified_only"]:
                raise UserUnverifiedError()

    def should_do_verification(self):
        return (
            (hasattr(self, "guild") and self.guild)
            and (hasattr(self, "channel") and self.channel)
            and (hasattr(self, "member") and self.member)
            and (hasattr(self, "ctx") and self.ctx)
        )

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
