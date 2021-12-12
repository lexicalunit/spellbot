import logging
from typing import Optional

from ddtrace import tracer
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashCommandOptionType

from .. import SpellBot
from ..interactions import ConfigInteraction
from ..utils import for_all_callbacks

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.guild_only())
class ConfigCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @cog_ext.cog_slash(
        name="power",
        description="Set your power level.",
        options=[
            {
                "name": "level",
                "description": "What is your current power level?",
                "required": False,
                "type": SlashCommandOptionType.INTEGER.value,
                "choices": [
                    {"name": "1", "value": 1},
                    {"name": "2", "value": 2},
                    {"name": "3", "value": 3},
                    {"name": "4", "value": 4},
                    {"name": "5", "value": 5},
                    {"name": "6", "value": 6},
                    {"name": "7", "value": 7},
                    {"name": "8", "value": 8},
                    {"name": "9", "value": 9},
                    {"name": "10", "value": 10},
                ],
            },
        ],
    )
    @tracer.wrap(name="command", resource="power")
    async def power(self, ctx: SlashContext, level: Optional[int] = None):
        async with self.bot.channel_lock(ctx.channel_id):
            async with ConfigInteraction.create(self.bot, ctx) as interaction:
                await interaction.power(level=level)


def setup(bot: SpellBot):
    bot.add_cog(ConfigCog(bot))
