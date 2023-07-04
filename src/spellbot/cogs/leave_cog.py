import logging

import discord
from ddtrace import tracer
from discord import app_commands
from discord.ext import commands

from .. import SpellBot
from ..actions import LeaveAction
from ..metrics import add_span_context
from ..utils import for_all_callbacks, is_guild

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
        add_span_context(interaction)
        async with LeaveAction.create(self.bot, interaction) as action:
            await action.execute()

    @app_commands.command(name="leave_all", description="Leaves all pending games.")
    @tracer.wrap(name="interaction", resource="leave_all_command")
    async def leave_all(self, interaction: discord.Interaction) -> None:
        add_span_context(interaction)
        async with LeaveAction.create(self.bot, interaction) as action:
            await action.execute_all()


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(LeaveGameCog(bot), guild=bot.settings.GUILD_OBJECT)
