# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from spellbot.actions import BlockAction
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_guild, traced_interaction

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from spellbot import SpellBot


@for_all_callbacks(app_commands.check(is_guild))
class BlockCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="block",
        description="Block another user from joining your games.",
    )
    @app_commands.describe(target="The user to block")
    @traced_interaction()
    async def block(
        self,
        interaction: discord.Interaction,
        target: discord.User | discord.Member,
    ) -> None:
        async with BlockAction.create(self.bot, interaction) as action:
            await action.block(target=target)

    @app_commands.command(
        name="unblock",
        description="Unblock a user you've previously blocked.",
    )
    @app_commands.describe(target="The user to unblock")
    @traced_interaction()
    async def unblock(
        self,
        interaction: discord.Interaction,
        target: discord.User | discord.Member,
    ) -> None:
        async with BlockAction.create(self.bot, interaction) as action:
            await action.unblock(target=target)

    @app_commands.command(
        name="blocked",
        description="Get a link to view and manage the users you've blocked.",
    )
    @traced_interaction()
    async def blocked(self, interaction: discord.Interaction) -> None:
        async with BlockAction.create(self.bot, interaction) as action:
            await action.blocked()


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(BlockCog(bot), guild=settings.GUILD_OBJECT)
