from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer
from discord import app_commands
from discord.ext import commands

from spellbot.actions import LeaveAction
from spellbot.metrics import add_span_context
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_guild

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_guild))
class LeaveGameCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    # Normally this function would be named "leave" to match the command name like
    # in all the other cogs. But in this case we're using `leave_command` to
    # differentiate it from the `leave` button in the LFG cog.
    @app_commands.command(name="leave", description="Leaves pending games in this channel.")
    @tracer.wrap(name="interaction", resource="leave_command")
    async def leave_command(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        async with (
            self.bot.guild_lock(interaction.guild.id),
            LeaveAction.create(self.bot, interaction) as action,
        ):
            await action.execute()

    @app_commands.command(name="leave_all", description="Leaves all pending games.")
    @tracer.wrap(name="interaction", resource="leave_all_command")
    async def leave_all(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        async with (
            self.bot.guild_lock(interaction.guild.id),
            LeaveAction.create(self.bot, interaction) as action,
        ):
            await action.execute_all()


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(LeaveGameCog(bot), guild=settings.GUILD_OBJECT)
