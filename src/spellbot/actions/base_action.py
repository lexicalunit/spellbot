# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, NoReturn, Self, cast

from ddtrace.trace import tracer

from spellbot import audit, services
from spellbot.database import DatabaseSession, db_session_manager
from spellbot.errors import (
    GuildBannedError,
    SpellBotError,
    UserBannedError,
)
from spellbot.i18n import guild_locale, user_locale
from spellbot.metrics import add_span_request_id, setup_ignored_errors

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import discord

    from spellbot import SpellBot
    from spellbot.data import ChannelData, GuildData, UserData

logger = logging.getLogger(__name__)


async def handle_exception(ex: Exception) -> NoReturn:
    if isinstance(ex, SpellBotError):
        raise ex
    # This is always called from an except handler, but not lexically inside one,
    # so pass exc_info explicitly rather than relying on logger.exception().
    logger.error(
        "error: rolling back database session due to unhandled exception: %s: %s",
        ex.__class__.__name__,
        ex,
        exc_info=ex,
    )
    await DatabaseSession.rollback()
    raise ex


class BaseAction:
    bot: SpellBot
    interaction: discord.Interaction
    member: discord.Member
    guild: discord.Guild | None
    channel: discord.TextChannel | None
    channel_data: ChannelData
    guild_data: GuildData | None
    user_data: UserData | None

    def __init__(self, bot: SpellBot, interaction: discord.Interaction) -> None:
        self.bot = bot
        self.interaction = interaction
        self.member = cast("discord.Member", self.interaction.user)
        self.guild = cast("discord.Guild", self.interaction.guild)
        self.channel = cast("discord.TextChannel", self.interaction.channel)

    async def upsert_request_objects(self) -> None:  # pragma: no cover
        self.guild_data: GuildData | None = None
        if self.guild:
            self.guild_data = await services.guilds.upsert(
                self.guild,
                locale=guild_locale(self.guild),
            )

        if self.guild_data and self.guild_data.banned:
            raise GuildBannedError

        if self.guild and self.channel:
            self.channel_data = await services.channels.upsert(self.channel)

        # Capture user's locale from the interaction to store in the database
        locale = user_locale(self.interaction)
        guild_xid = self.guild.id if self.guild else None
        self.user_data = await services.users.upsert(
            self.member,
            guild_xid=guild_xid,
            locale=locale,
        )

        if self.user_data.banned:
            raise UserBannedError

    @classmethod
    @asynccontextmanager
    async def create(
        cls,
        bot: SpellBot,
        interaction: discord.Interaction,
    ) -> AsyncGenerator[Self]:
        action = cls(bot, interaction)
        with tracer.trace(name=f"spellbot.interactions.{cls.__name__}.create") as span:
            setup_ignored_errors(span)
            add_span_request_id(str(interaction.id))
            async with db_session_manager():
                try:
                    await action.upsert_request_objects()
                    # Attribute any settings changes this action makes to the acting user. The
                    # auto-upserts above are intentionally left outside this scope so they stay
                    # unattributed. See spellbot.audit.
                    with audit.actor(  # pragma: no branch
                        interaction.user.id,
                        getattr(interaction.user, "display_name", None),
                        audit.SOURCE_DISCORD,
                    ):
                        yield action
                except Exception as ex:  # pragma: no cover
                    await handle_exception(ex)
