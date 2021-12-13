import logging

from ddtrace import tracer
from discord.ext import commands
from discord_slash import SlashContext, cog_ext

from .. import SpellBot
from ..interactions import LeaveInteraction
from ..metrics import add_span_context
from ..utils import for_all_callbacks

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.guild_only())
class LeaveGameCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    # Normally this function would be named "leave" to match the command name like
    # in all the other cogs. But in this case we're using `leave_command` to
    # differentiate it from the `leave` button in the LFG cog, which must be called
    # leave in order for the button's custom_id hook to work properly.
    @cog_ext.cog_slash(name="leave", description="Leaves any game that you are in.")
    @tracer.wrap(name="interaction", resource="leave_command")
    async def leave_command(self, ctx: SlashContext):
        add_span_context(ctx)
        async with LeaveInteraction.create(self.bot, ctx) as interaction:
            await interaction.execute()


def setup(bot: SpellBot):
    bot.add_cog(LeaveGameCog(bot))
