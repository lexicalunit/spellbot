import logging
from typing import Optional

from ddtrace import tracer
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.context import ComponentContext
from discord_slash.model import SlashCommandOptionType

from .. import SpellBot
from ..interactions.leave_interaction import LeaveInteraction
from ..interactions.lfg_interaction import LookingForGameInteraction
from ..models import GameFormat
from ..utils import for_all_callbacks

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.guild_only())
class LookingForGameCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @cog_ext.cog_component()
    @tracer.wrap(name="command", resource="leave")
    async def leave(self, ctx: ComponentContext):
        async with self.bot.channel_lock(ctx.channel_id):
            async with LeaveInteraction.create(self.bot, ctx) as interaction:
                await interaction.execute(origin=True)

    @cog_ext.cog_component()
    @tracer.wrap(name="command", resource="join")
    async def join(self, ctx: ComponentContext):
        assert ctx.origin_message_id
        async with self.bot.channel_lock(ctx.channel_id):
            async with LookingForGameInteraction.create(self.bot, ctx) as interaction:
                await interaction.execute(message_xid=ctx.origin_message_id)

    @cog_ext.cog_component()
    @tracer.wrap(name="command", resource="points")
    async def points(self, ctx: ComponentContext):
        await ctx.defer(ignore=True)
        assert ctx.origin_message
        assert ctx.selected_options
        assert isinstance(ctx.selected_options, list)
        points = int(ctx.selected_options[0])
        async with LookingForGameInteraction.create(self.bot, ctx) as interaction:
            await interaction.add_points(ctx.origin_message, points)

    @cog_ext.cog_slash(
        name="lfg",
        description="Looking for game.",
        options=[
            {
                "name": "friends",
                "description": "Mention friends to join this game with.",
                "required": False,
                "type": SlashCommandOptionType.STRING.value,
            },
            {
                "name": "seats",
                "description": "How many players can be seated at this game?",
                "required": False,
                "type": SlashCommandOptionType.INTEGER.value,
                "choices": [
                    {"name": "2 players", "value": 2},
                    {"name": "3 players", "value": 3},
                    {"name": "4 players", "value": 4},
                ],
            },
            {
                "name": "format",
                "description": "What game format do you want to play?",
                "required": False,
                "type": SlashCommandOptionType.INTEGER.value,
                "choices": [
                    {
                        "name": str(format),
                        "value": format.value,
                    }
                    for format in GameFormat
                ],
            },
        ],
    )
    @tracer.wrap(name="command", resource="lfg")
    async def lfg(
        self,
        ctx: SlashContext,
        friends: Optional[str] = None,
        seats: Optional[int] = None,
        format: Optional[int] = None,
    ):
        async with self.bot.channel_lock(ctx.channel_id):
            async with LookingForGameInteraction.create(self.bot, ctx) as interaction:
                await interaction.execute(friends=friends, seats=seats, format=format)


def setup(bot: SpellBot):
    bot.add_cog(LookingForGameCog(bot))
