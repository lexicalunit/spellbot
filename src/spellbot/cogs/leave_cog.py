import logging

from ddtrace import tracer
from discord.ext import commands
from discord_slash import SlashContext, cog_ext

from .. import SpellBot
from ..interactions import LeaveInteraction
from ..utils import for_all_callbacks

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.guild_only())
class LeaveGameCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @cog_ext.cog_slash(name="leave", description="Leaves any game that you are in.")
    @tracer.wrap(name="command", resource="leave")
    async def leave(self, ctx: SlashContext):
        async with LeaveInteraction.create(self.bot, ctx) as interaction:
            await interaction.execute()


def setup(bot: SpellBot):
    bot.add_cog(LeaveGameCog(bot))
