import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional, Type, TypeVar, cast

import discord
from asgiref.sync import sync_to_async
from discord_slash.context import InteractionContext
from sqlalchemy.engine.base import Transaction

from spellbot.client import SpellBot
from spellbot.database import DatabaseSession, connection
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
    # Main thread data members, only use outside of sync_to_async code!
    bot: SpellBot
    services: ServicesRegistry
    ctx: Optional[InteractionContext]
    member: Optional[discord.Member]
    guild: Optional[discord.Guild]
    channel: Optional[discord.TextChannel]

    # Thread sensitive data members, only use within sync_to_async code!
    transaction: Transaction

    def __init__(self, bot: SpellBot, ctx: Optional[InteractionContext] = None):
        self.bot = bot
        self.services = ServicesRegistry()
        self.ctx = ctx
        if self.ctx:
            self.member = cast(discord.Member, self.ctx.author)
            self.guild = cast(discord.Guild, self.ctx.guild)
            self.channel = cast(discord.TextChannel, self.ctx.channel)

    @sync_to_async
    def begin_session(self):
        self.transaction = connection.begin()
        DatabaseSession()

    @sync_to_async
    def handle_exception(self, ex):
        if isinstance(ex, (SpellbotAdminOnly, UserBannedError)):
            raise ex
        logger.exception(
            "error: rolling back database transaction due to unhandled exception: %s: %s",
            ex.__class__.__name__,
            ex,
        )
        self.transaction.rollback()
        raise ex

    @sync_to_async
    def end_session(self):
        self.transaction.commit()
        DatabaseSession.remove()

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
        try:
            await interaction.begin_session()
            if ctx:
                await interaction.services.guilds.upsert(interaction.guild)
                await interaction.services.channels.upsert(interaction.channel)
                await interaction.services.users.upsert(interaction.member)
                if await interaction.services.users.is_banned(ctx.author_id):
                    raise UserBannedError()
            yield interaction
        except Exception as ex:
            await interaction.handle_exception(ex)
        finally:
            await interaction.end_session()
