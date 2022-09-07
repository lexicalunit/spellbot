import logging
from typing import Optional

import discord
from ddtrace import tracer
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from .. import SpellBot
from ..actions import ConfigAction
from ..metrics import add_span_context
from ..utils import for_all_callbacks, is_guild

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_guild))
class ConfigCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @app_commands.command(
        name="power",
        description="Set your power level.",
    )
    @app_commands.describe(level="What is your current power level?")
    @app_commands.choices(
        level=[
            Choice(name="1", value=1),
            Choice(name="2", value=2),
            Choice(name="3", value=3),
            Choice(name="4", value=4),
            Choice(name="5", value=5),
            Choice(name="6", value=6),
            Choice(name="7", value=7),
            Choice(name="8", value=8),
            Choice(name="9", value=9),
            Choice(name="10", value=10),
        ],
    )
    @tracer.wrap(name="interaction", resource="power")
    async def power(self, interaction: discord.Interaction, level: Optional[int] = None) -> None:
        assert interaction.channel_id is not None
        add_span_context(interaction)
        async with self.bot.channel_lock(interaction.channel_id):
            async with ConfigAction.create(self.bot, interaction) as action:
                await action.power(level=level)


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(ConfigCog(bot), guild=bot.settings.GUILD_OBJECT)
