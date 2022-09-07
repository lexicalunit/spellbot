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
    def __init__(self, bot: SpellBot):
        self.bot = bot

    # Normally this function would be named "leave" to match the command name like
    # in all the other cogs. But in this case we're using `leave_command` to
    # differentiate it from the `leave` button in the LFG cog.
    @app_commands.command(name="leave", description="Leaves any game that you are in.")
    @tracer.wrap(name="interaction", resource="leave_command")
    async def leave_command(self, interaction: discord.Interaction) -> None:
        add_span_context(interaction)
        async with LeaveAction.create(self.bot, interaction) as action:
            await action.execute()


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(LeaveGameCog(bot), guild=bot.settings.GUILD_OBJECT)
