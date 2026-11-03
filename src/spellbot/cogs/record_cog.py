# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from spellbot.actions import RecordAction
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_guild, traced_interaction

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_guild))
class RecordCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="record",
        description="View your or another user's play history across all servers.",
    )
    @app_commands.describe(user="Mention another user to see their history instead of your own")
    @traced_interaction()
    async def record(
        self,
        interaction: discord.Interaction,
        user: discord.User | discord.Member | None = None,
    ) -> None:
        async with RecordAction.create(self.bot, interaction) as action:
            await action.execute(target=user or interaction.user)

    @app_commands.command(
        name="history",
        description="View historical game records in this channel.",
    )
    @traced_interaction()
    async def history(self, interaction: discord.Interaction) -> None:
        async with RecordAction.create(self.bot, interaction) as action:
            await action.history()

    @app_commands.command(name="top", description="View the top players in this channel.")
    @app_commands.describe(monthly="Ranks for this month only?")
    @app_commands.describe(ago="How many months ago?")
    @traced_interaction()
    async def top(
        self,
        interaction: discord.Interaction,
        monthly: bool = True,
        ago: int = 0,
    ) -> None:
        async with RecordAction.create(self.bot, interaction) as action:
            await action.top(monthly, ago)


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(RecordCog(bot), guild=settings.GUILD_OBJECT)
