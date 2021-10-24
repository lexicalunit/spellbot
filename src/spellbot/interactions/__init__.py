import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional, Type, TypeVar, cast

import discord
from asgiref.sync import sync_to_async
from discord_slash.context import InteractionContext

from spellbot.client import SpellBot
from spellbot.database import DatabaseSession, db_session_manager
from spellbot.errors import SpellbotAdminOnly, UserBannedError

logger = logging.getLogger(__name__)


class ServicesRegistry:
    def __init__(self):
        from spellbot.services.awards import AwardsService
        from spellbot.services.channels import ChannelsService
        from spellbot.services.games import GamesService
        from spellbot.services.guilds import GuildsService
        from spellbot.services.plays import PlaysService
        from spellbot.services.users import UsersService
        from spellbot.services.verifies import VerifiesService

        self.awards = AwardsService()
        self.channels = ChannelsService()
        self.games = GamesService()
        self.guilds = GuildsService()
        self.plays = PlaysService()
        self.users = UsersService()
        self.verifies = VerifiesService()


InteractionType = TypeVar("InteractionType", bound="BaseInteraction")


class BaseInteraction:
    bot: SpellBot
    services: ServicesRegistry
    ctx: Optional[InteractionContext]
    member: Optional[discord.Member]
    guild: Optional[discord.Guild]
    channel: Optional[discord.TextChannel]

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

    @classmethod
    @asynccontextmanager
    async def create(
        cls: Type[InteractionType],
        bot: SpellBot,
        ctx: Optional[InteractionContext] = None,
    ) -> AsyncGenerator[InteractionType, None]:
        if ctx:
            interaction = cls(bot, ctx)
        else:
            interaction = cls(bot)
        async with db_session_manager():
            try:
                if ctx:
                    await interaction.services.guilds.upsert(interaction.guild)
                    await interaction.services.channels.upsert(interaction.channel)
                    await interaction.services.users.upsert(interaction.member)
                    if await interaction.services.users.is_banned(ctx.author_id):
                        raise UserBannedError()
                yield interaction
            except Exception as ex:
                await interaction.handle_exception(ex)
