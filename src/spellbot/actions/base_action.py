# pylint: disable=wrong-import-order
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, NoReturn, Optional, Type, TypeVar, cast

import discord
from asgiref.sync import sync_to_async
from ddtrace import tracer

from .. import SpellBot
from ..database import DatabaseSession, db_session_manager
from ..errors import SpellBotError, UserBannedError, UserUnverifiedError, UserVerifiedError
from ..metrics import setup_ignored_errors
from ..services import ServicesRegistry
from ..utils import user_can_moderate

logger = logging.getLogger(__name__)

ActionType = TypeVar("ActionType", bound="BaseAction")


@sync_to_async
def handle_exception(ex: Exception) -> NoReturn:
    if isinstance(ex, SpellBotError):
        raise ex
    logger.exception(
        "error: rolling back database session due to unhandled exception: %s: %s",
        ex.__class__.__name__,
        ex,
    )
    DatabaseSession.rollback()
    raise ex


class BaseAction:
    bot: SpellBot
    services: ServicesRegistry
    interaction: discord.Interaction
    member: discord.Member
    guild: Optional[discord.Guild]
    channel: Optional[discord.TextChannel]
    channel_data: dict[str, Any]

    def __init__(self, bot: SpellBot, interaction: discord.Interaction):
        self.bot = bot
        self.services = ServicesRegistry()
        self.interaction = interaction
        self.member = cast(discord.Member, self.interaction.user)
        self.guild = cast(discord.Guild, self.interaction.guild)
        self.channel = cast(discord.TextChannel, self.interaction.channel)

    async def upsert_request_objects(self) -> None:
        if self.guild:
            await self.services.guilds.upsert(self.guild)

        if self.guild and self.channel:
            self.channel_data = await self.services.channels.upsert(self.channel)

        await self.services.users.upsert(self.member)

        if await self.services.users.is_banned(self.member.id):
            raise UserBannedError()

        if self.should_do_verification():
            await self.handle_verification()

    async def handle_verification(self) -> None:
        if not self.guild:
            return
        verified: Optional[bool] = None
        if self.channel_data["auto_verify"]:
            verified = True
        await self.services.verifies.upsert(self.guild.id, self.interaction.user.id, verified)
        if not user_can_moderate(self.interaction.user, self.guild, self.channel):
            user_is_verified = await self.services.verifies.is_verified()
            if user_is_verified and self.channel_data["unverified_only"]:
                raise UserVerifiedError()
            if not user_is_verified and self.channel_data["verified_only"]:
                raise UserUnverifiedError()

    def should_do_verification(self) -> bool:
        return bool(self.guild and self.channel)

    @classmethod
    @asynccontextmanager
    async def create(
        cls: Type[ActionType],
        bot: SpellBot,
        interaction: discord.Interaction,
    ) -> AsyncGenerator[ActionType, None]:
        action = cls(bot, interaction)
        with tracer.trace(name=f"spellbot.interactions.{cls.__name__}.create") as span:
            setup_ignored_errors(span)
            async with db_session_manager():
                try:
                    await action.upsert_request_objects()
                    yield action
                except Exception as ex:
                    await handle_exception(ex)
